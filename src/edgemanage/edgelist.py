from const import DECISION_SLICE_WINDOW

import logging
import time
from collections import Counter
import random
import socket
import time
import os

from jinja2 import Environment, PackageLoader, FileSystemLoader

try:
    env = Environment(loader=PackageLoader('edgemanage','templates'))
except ImportError as e:
    # we're not installed as a module
    if os.path.exists("edgemanage/templates") and os.path.isdir("edgemanage/templates"):
        env = Environment(loader=FileSystemLoader("edgemanage/templates"))
    elif os.path.exists("templates") and os.path.isdir("templates"):
        env = Environment(loader=FileSystemLoader("templates"))
    else:
        raise

class EdgeList(object):
    """ A class that represents a list of edges """

    def __init__(self):
        # A dictionary indicating whether an edge is live or not, and
        # what state it's in
        self.edges = {}

    def add_edge(self, edgename, state=None, live=False):
        self.edges[edgename] = {
            "live": live,
            "state": state
        }

    def __len__(self):
        return len(self.edges.keys())

    def get_state_stats(self):
        counter = Counter([ edge["state"] for edge in self.edges.values() ])
        return dict(counter)

    def get_live_count(self):
        return len(self.get_live_edges())

    def get_live_edges(self):
        return self.get_edges_by_liveness(True)

    def get_unlive_edges(self):
        return self.get_edges_by_liveness(False)

    def is_live(self, edgename):
        if edgename in self.edges:
            return self.edges[edgename]["live"]
        else:
            return None

    def get_edges_by_liveness(self, islive):
        edge_list = []
        for edge, state_dict in self.edges.iteritems():

            if state_dict["live"] == islive:
                edge_list.append(edge)
        return sorted(edge_list)

    def set_edge_live(self, edgename):
        self.edges[edgename]["live"] = True

    def set_live_by_state(self, state, desired_count):

        # return value that indicates whether we satisfied the
        # condition of setting $desired_count hosts of $state to live
        met_demand = False
        edge_list = self.get_edges(state)
        random.shuffle(edge_list)
        for edge in edge_list:
            if self.get_live_count() == desired_count:
                logging.debug("Edgelist got enough (%d) edges in state %s",
                              desired_count, state)
                met_demand = True
                break
            self.set_edge_live(edge)

        return met_demand

    def get_edges(self, state=None):
        ''' return a list of edges, with the option to filter by state '''
        if state:
            return [ edge for edge in self.edges if self.edges[edge]['state'] == state ]
        else:
            return self.edges.keys()

    def get_random_edge(self, state=None):
        selected_edges = self.get_edges(state)
        random.shuffle(selected_edges)
        if state:
            return selected_edges[0]

    def generate_zone(self, domain, zonefile_dir, dns_config,
                      serial_number=None):
        logging.debug("Started generating zone for %s", domain)

        if not all([ i.endswith(".") for i in dns_config["ns_records"] ]):
            raise Exception(("Nameserver list is incorrectly formatted. Every"
                             " entry should end with a full stop"))

        rotate_zones = []
        if "rotate_zones" in dns_config:
            rotate_zones = dns_config["rotate_zones"]

        live_edge_ips = []
        for live_edge in self.get_live_edges():
            try:
                edge_ip = socket.gethostbyname(live_edge)
                live_edge_ips.append(edge_ip)
            except socket.gaierror as e:
                try:
                    # Retry resolution failures
                    edge_ip = socket.gethostbyname(live_edge)
                    live_edge_ips.append(edge_ip)
                except socket.gaierror as e:
                    logging.error(("Failed to resolve IP address for %s! Correct"
                                   " hostname or remove this IP address from rotation."),
                                  live_edge)
                    continue

        logging.debug("Writing zone file for %s, live edge list is %s",
                      domain, self.get_live_edges())

        with open(os.path.join(zonefile_dir, "%s.zone" % domain)) as zonefile_f:
            zonefile = zonefile_f.read()

        if not serial_number:
            serial_number = int(time.time())
        template = env.get_template('zonetemplate.j2')
        return template.render(
            zonefile=zonefile,
            domain=domain,
            live_edge_ips=live_edge_ips,
            rotate_zones=rotate_zones,
            serial_number=serial_number,
            soa_mailbox=dns_config["soa_mailbox"],
            soa_nameserver=dns_config["soa_nameserver"],
            nameservers=dns_config["ns_records"]
        )
