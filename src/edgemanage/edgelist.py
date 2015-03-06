EDGE_DICT = {"live": False}

import socket
import time
import os

from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('templates'))

class EdgeList(object):
    """ A class that represents a list of edges """

    def __init__(self, upper_domain):
        self.upper_domain = upper_domain
        self.edges = {}

    def add_edge(self, edgename):
        self.edges[edgename] = EDGE_DICT.copy()

    def make_active(self, edgename):
        self.edges[edgename]["live"] = True
        return True

    def make_inactive(self, edgename):
        self.edges[edgename]["live"] = False
        return False

    def generate_zone(self, domain, zonefile_dir, dns_config, serial_number=None):
        if not all([ i.endswith(".") for i in dns_config["ns_records"] ]):
            raise Exception(("Nameserver list is incorrectly formatted. Every"
                             " entry should end with a full stop"))

        live_edge_ips = [ socket.gethostbyname("%s.%s" % (i,self.upper_domain)) \
                          for i in self.edges if self.edges[i]["live"] ]

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
