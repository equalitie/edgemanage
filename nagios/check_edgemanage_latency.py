#!/usr/bin/env python

import sys
import time
import json
import argparse
import os.path

import yaml

from edgemanage.const import CONFIG_PATH

DEFAULT_CRIT = 2.0
DEFAULT_WARN = 4.0

OUTPUT_LABEL="ACTIVE_EDGE_LATENCY"
STATUS_MAP = {0: "OK",
              1: "WARN",
              2: "CRIT",
              3: "UKNOWN"}

class CheckLatency(object):

    def __init__(self, edgehealth_dir, edge_list, check_all=False, verbose=False):
        self.latency_map = {}
        self.now = time.time()

        for edge_name in edge_list:
            with open(os.path.join(edgehealth_dir, "%s.edgestore" % edge_name)) as health_f:
                health_json = json.loads(health_f.read())
                if "fetch_times" not in health_json or not health_json["fetch_times"]:
                    # Skip uninitialised edges, or edges that have no data
                    continue

                if not check_all and health_json["state"] != "in":
                    # if we're not explicitly checking all, then only check hosts that are in.
                    continue

                latest_fetch_time = sorted(health_json["fetch_times"].keys())[-1]
                self.latency_map[edge_name] = health_json["fetch_times"][latest_fetch_time]

    def check_rotation(self, warn, crit):
        worst_latency = None
        nagios_status = 0
        edge_name = None
        for edge_name, fetch_value in self.latency_map.iteritems():
            if not worst_latency or fetch_value > worst_latency:
                worst_latency = fetch_value
                edge_name = edge_name
        if not worst_latency:
            nagios_message = "No fetch data!"
            nagios_status = 3
        elif worst_latency >= crit:
            nagios_status = 2
        elif worst_latency >= warn:
            nagios_status = 1
        nagios_message = "Slowest active edge responded in %f" % worst_latency

        if edge_name:
            return (nagios_status, "%s %s %s | slowestactive=%f edge=%s" % (OUTPUT_LABEL,
                                                                   STATUS_MAP[nagios_status],
                                                                   nagios_message, worst_latency,
                                                                   edge_name))
        else:
            return (3, "no edgemanage data for time window")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Nagios check for Edgemanage fetch latency.')
    parser.add_argument("--config", "-c", dest="config_path", action="store",
                        help="Path to configuration file (defaults to %s)" % CONFIG_PATH,
                        default=CONFIG_PATH)
    parser.add_argument("--warn", "-w", action="store", dest="warn",
                        help="Latency to trigger WARN level at",
                        default=DEFAULT_WARN, type=float)
    parser.add_argument("--critical", "-C", action="store", dest="crit",
                        help="Latency to trigger CRIT level at",
                        default=DEFAULT_CRIT, type=float)
    parser.add_argument("--all", "-a", action="store_true", dest="all",
                        help="Check latency across all hosts, not just the current \"in\" hosts",
                        default=False)
    parser.add_argument("--verbose", "-v", dest="verbose", action="store_true",
                        help="Verbose output", default=False)
    parser.add_argument("--dnet", "-A", dest="dnet", action="store",
                        help="Specify DNET (mandatory)", required=True)
    args = parser.parse_args()

    with open(args.config_path) as config_f:
        config = yaml.safe_load(config_f.read())

    if not os.path.isdir(config["healthdata_store"]):
        raise Exception("Argument must be a directory full of edge health files")

    # TODO: extra edge list?
    with open(os.path.join(config["edgelist_dir"], args.dnet)) as edge_f:
        edge_list = [ i.strip() for i in edge_f.read().split("\n") if i.strip() and not i.startswith("#") ]

    with open(os.path.join(config["extra_edgelist_dir"], args.dnet)) as edge_f:
        extra_edge_list = [ i.strip() for i in edge_f.read().split("\n") if i.strip() and not i.startswith("#") ]

    edge_list += extra_edge_list

    c = CheckLatency(config["healthdata_store"], edge_list, args.all, verbose=args.verbose)
    status, message = c.check_rotation(args.warn, args.crit)
    print message
    sys.exit(status)
