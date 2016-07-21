#!/usr/bin/env python
import os
import glob
import shutil
import unittest
import tempfile
import yaml
import logging
import pdb

import pexpect

# Offset ID for the canary edges on the web server
CANARY_ID_OFFSET = 100
DNET_NAME = 'mynet'


class EdgeManageIntegration(unittest.TestCase):
    """
    Integration test for `edge_manage` script against running web
    servers.
    """
    def setUp(self):
        self.edge_data_dir = tempfile.mkdtemp()

    def rewrite_default_config(self, options=None, num_edges=20, num_canaries=20):
        """
        Rewrite the default config file to use this test environment.
        """
        with open('conf/edgemanage.yaml') as default_conf:
            config = yaml.load(default_conf.read())

        # Configure the test object
        config['testobject']['proto'] = 'http'
        config['testobject']['port'] = '5000'
        config['testobject']['uri'] = '/test_object'
        config['testobject']['local'] = os.path.abspath('tests/test_data/edge_test_object.txt')

        # Set testing flag in integration tests, this will cause the raw IP to be sent
        # in the Host header so it can be read by the testng web server.
        config['testing'] = True

        config['healthdata_store'] = os.path.join(self.edge_data_dir, 'health')
        os.mkdir(config['healthdata_store'])

        config['edgelist_dir'] = os.path.join(self.edge_data_dir, 'edges')
        os.mkdir(config['edgelist_dir'])

        # Create flat file with list of edge IPs file
        for net in [DNET_NAME]:
            with open(os.path.join(config['edgelist_dir'], net), 'w') as edge_file:
                for edge in range(0, num_edges):
                    edge_file.write('127.0.0.%d\n' % (edge+1))

        config['canary_files'] = '%s/canaries/{dnet}' % self.edge_data_dir
        os.mkdir(os.path.join(self.edge_data_dir, 'canaries'))

        # XXX: Create canaries file
        for net in [DNET_NAME]:
            with open('%s/canaries/%s' % (self.edge_data_dir, net), 'w') as canary_file:
                for canary in range(CANARY_ID_OFFSET, CANARY_ID_OFFSET + num_canaries):
                    canary_file.write('canary%d.com: 127.0.0.%d\n' % (canary+1, canary+1))

        config['statefile'] = '%s/{dnet}.state' % self.edge_data_dir
        config['logpath'] = '%s/edgemanage.log' % self.edge_data_dir
        config['lockfile'] = '%s/edgemanage.lock' % self.edge_data_dir
        del config['commands']['run_after_changes']
        del config['commands']['run_after']

        # Override config with custom options
        if options:
            config.update(options)

        # Write modified config to a file
        new_config_filename = os.path.join(self.edge_data_dir, 'edgemanage.conf')
        with open(new_config_filename, 'w') as config_file:
            config_file.write(yaml.dump(config, default_flow_style=False))
        return os.path.abspath(new_config_filename)

    def load_all_health_files(self):
        """
        Load the health files for each edge into a dictionary to be checked
        """
        health_data = {}
        for health_file_path in glob.glob('%s/health/*.edgestore' % self.edge_data_dir):
            filename = health_file_path.split('/')[-1]
            edge_ip = filename.split('.edgestore')[0]
            with open(health_file_path, 'r') as health_file:
                edge_data = yaml.load(health_file.read())

                # Load the most recent fetch time measurement
                most_recent_fetch = sorted(edge_data['fetch_times'])[0]
                health_data[edge_ip] = {
                    'health': edge_data['health'],
                    'mode': edge_data['mode'],
                    'fetch_time': edge_data['fetch_times'][most_recent_fetch],
                }
        return health_data

    def load_state_file(self):
        """
        Parse the state file generate by edge_manage
        """
        with open('%s/%s.state' % (self.edge_data_dir, DNET_NAME), 'r') as state_file:
            return yaml.load(state_file.read())

    def spawn_web_server(self, config_file=None, test_object=None):
        """
        Spawn a Flask testing server and wait for it to be ready.
        """
        test_server_command = ['python testing_server.py']
        if config_file:
            test_server_command.extend(['--edge-config', config_file])
        if test_object:
            test_server_command.extend(['--test-object', test_object])

        self.web_process = pexpect.spawn(' '.join(test_server_command), cwd="tests/")
        self.web_process.expect("Test server running", timeout=5)

    def run_edge_manage(self, config_path, debug=False):
        """
        Run the edge_manage tool and wait for it to finish
        """
        edge_manage_command = ['edge_manage', '-A', DNET_NAME,
                               '--config', config_path]
        if debug:
            edge_manage_command.append('--verbose')

        # Run and wait for command to finish
        em_process = pexpect.spawn(' '.join(edge_manage_command), timeout=60)
        em_process.expect(pexpect.EOF)
        em_process.close()
        self.assertEqual(em_process.exitstatus, 0)

        if debug:
            # output = '\n'.join(em_process.before.split('\r\n'))
            pdb.set_trace()
        return em_process.before

    def test20Edges20CanariesAllFast(self):
        """
        Run edge_manage against fast edges and canaries, all should be healthy.
        """
        self.spawn_web_server('test_server_configs/20-edge-20-canaries-all-fast.yaml')
        config_path = self.rewrite_default_config(num_edges=20, num_canaries=20)

        # Run edge_manage
        self.run_edge_manage(config_path)

        state_data = self.load_state_file()
        self.assertTrue(len(state_data['last_live']), 4)

        health_data = self.load_all_health_files()
        self.assertEqual(len(health_data), 40)
        self.assertTrue(all([edge['health'] == "pass" for edge in health_data.values()]))

    def test20Edges20CanariesAll3Seconds(self):
        """
        Run edge_manage against slow edges and canaries which take 3 seconds
        to respond. The request timeout is set to 2 seconds to make this test
        run faster.

        All edges and canaries should timeout and be set as unavailable.
        """
        self.spawn_web_server('test_server_configs/20-edge-20-canaries-all-3-seconds.yaml')
        custom_options = {'timeout': 2}
        config_path = self.rewrite_default_config(options=custom_options,
                                                  num_edges=20, num_canaries=20)

        self.run_edge_manage(config_path)
        state_data = self.load_state_file()
        self.assertEqual(len(state_data['last_live']), 0)

        # Confirm that all edges were not healthy
        health_data = self.load_all_health_files()
        self.assertTrue(all([edge['health'] == "fail" for edge in health_data.values()]))

    def tearDown(self):
        # Stop the Flask server
        try:
            self.web_process.close()
        except AttributeError:
            logging.exception("No web_process found.")
        shutil.rmtree(self.edge_data_dir)

if __name__ == '__main__':
    unittest.main()
