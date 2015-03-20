from const import DECISION_SLICE_WINDOW

import logging
import time
import socket
import time
import os

from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('edgemanage/templates'))

class EdgeList(object):
    """ A class that represents a list of edges """

    def __init__(self):
        self.edges = []

    def add_edge(self, edgename):
        self.edges.append(edgename)

    def generate_zone(self, domain, zonefile_dir, dns_config, serial_number=None):
        if not all([ i.endswith(".") for i in dns_config["ns_records"] ]):
            raise Exception(("Nameserver list is incorrectly formatted. Every"
                             " entry should end with a full stop"))

        live_edge_ips = [ socket.gethostbyname("%s" % i) for i in self.edges ]

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
