#!/usr/bin/env python

from edgemanage import const
from edgemanage import edgetest

import os
import yaml
import argparse
import hashlib
from concurrent.futures import ProcessPoolExecutor, as_completed

def future_fetch(edgetest, testobject_host, testobject_path, testobject_proto):
    return {edgetest.edgename: edgetest.fetch(testobject_host, testobject_path, testobject_proto)}

def main(dnet, dry_run, verbose, config):
    with open(os.path.join(config["edgelist_dir"], dnet)) as edge_f:
        edge_list = [ i for i in edge_f.read().split("\n") if i.strip() ]
    if verbose:
        print "Edge list is %s" % str(edge_list)

    testobject_proto = config["testobject"]["proto"]
    testobject_host = config["testobject"]["host"]
    testobject_path = config["testobject"]["uri"]

    with open(config["testobject"]["local"]) as test_local_f:
        testobject_hash = hashlib.md5(test_local_f.read()).hexdigest()

    edgescore_futures = []

    with ProcessPoolExecutor() as executor:
        for edgename in edge_list:
            edge_t = edgetest.EdgeTest(edgename, testobject_hash)
            edgescore_futures.append(executor.submit(future_fetch, edge_t, testobject_host, testobject_path, testobject_proto))

    resultdict = {}
    for f in as_completed(edgescore_futures):
        resultdict.update(f.result())
    for edgename, time_taken in resultdict.iteritems():
        print "Time for %s - %f" % (edgename, time_taken)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Manage Deflect edge status.')
    parser.add_argument("--dnet", "-A", dest="dnet", action="store",
                        help="Specify DNET (mandatory)")
    parser.add_argument("--config", "-c", dest="config_path", action="store",
                        help="Path to configuration file (defaults to %s)" % const.CONFIG_PATH,
                        default=const.CONFIG_PATH)
    parser.add_argument("--dry-run", "-n", dest="dryrun", action="store_true",
                        help="Dry run - don't generate any files", default=False)
    parser.add_argument("--verbose", "-v", dest="verbose", action="store_true",
                        help="Verbose output", default=False)
    args = parser.parse_args()

    with open(args.config_path) as config_f:
        config = yaml.safe_load(config_f.read())

    if not args.dnet:
        raise AttributeError("DNET is a mandatory option")
    main(args.dnet, args.dryrun, args.verbose, config)
