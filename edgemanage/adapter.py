"""
Non-commandline adapter, work with Django
"""

from edgemanage import util

import logging
import logging.handlers
import yaml
import os


class EdgemanageAdapter(object):

    def __init__(self, config_path, dnet):
        """
        Init adapter with `config`, `edge_list`
        """

        # load config
        with open(config_path) as config_f:
            self.config = yaml.safe_load(config_f.read())

        # load edge list
        with open(os.path.join(self.config["edgelist_dir"], dnet)) as edge_f:
            self.edge_list = [i.strip() for i in edge_f.read().split("\n")
                              if i.strip() and not i.startswith("#")]

    def get_config(self, config_str):
        return self.config[config_str] if config_str in self.config else None


    def edge_data_exist(self, edgename):
        return os.path.exists(os.path.join(self.config["healthdata_store"],
                                           "%s.edgestore" % edgename))


    def log_edge_conf(self, edgename, mode, comment):
        handler = logging.handlers.SysLogHandler(
            facility=logging.handlers.SysLogHandler.LOG_DAEMON)
        logger = logging.getLogger('edge_conf')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.info("Edge %s changed mode to %s with comment %s",
                    edgename, mode, comment)


    def lock_edge_conf(self):
        """
        Create a lock file for edge_conf
        """
        self.lock_f = open(self.config["lockfile"], "w")

        if not util.acquire_lock(self.lock_f):
            return False, "Couldn't acquire edge_conf lockfile"

        return True


    def unlock_edge_conf(self):
        """
        Close the lock file
        """
        self.lock_f.close()
