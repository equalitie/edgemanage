from const import DECISION_SLICE_WINDOW

import logging
import time
from collections import Counter
import random
import socket
import time
import os

from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('edgemanage/templates'))

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

    def get_state_stats(self):
        counter = Counter([ edge["state"] for edge in self.edges.values() ])
        return dict(counter)

    def get_live_count(self):
        return len(self.get_live_edges())

    def get_live_edges(self):
        edge_list = []
        for edge, state_dict in self.edges.iteritems():
            if state_dict["live"]:
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

    def generate_zone(self, domain, zonefile_dir, dns_config, serial_number=None):
        if not all([ i.endswith(".") for i in dns_config["ns_records"] ]):
            raise Exception(("Nameserver list is incorrectly formatted. Every"
                             " entry should end with a full stop"))

        live_edge_ips = [ socket.gethostbyname("%s" % i) for i in self.edges \
            if self.edges[i]["state"] == "live" ]

        with open(os.path.join(zonefile_dir, "%s.zone" % domain)) as zonefile_f:
            zonefile = zonefile_f.read()

        if not serial_number:
            serial_number = time.time()
        template = env.get_template('zonetemplate.j2')
        return template.render(
            zonefile=zonefile,
            domain=domain,
            live_edge_ips=live_edge_ips,
            serial_number=serial_number,
            soa_mailbox=dns_config["soa_mailbox"],
            soa_nameserver=dns_config["soa_nameserver"],
            nameservers=dns_config["ns_records"]
        )
