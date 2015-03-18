#!/usr/bin/env python

from edgemanage import const, EdgeTest, StatStore, DecisionMaker, StateFile

import json
import time
import os
import sys
import yaml
import argparse
import logging
import hashlib
import fcntl
import pprint
from concurrent.futures import ProcessPoolExecutor, as_completed

def nagios_output(lastrotation):
    time_now = time.time()
    nagios_status = "OK"
    if lastrotation:
        nagios_message = "Last rotation was %d ago" % (time_now - lastrotation)
    if not lastrotation:
        nagios_status = "UNKNOWN"
        nagios_message = "No last rotation time"
    elif (time_now - lastrotation) < const.NAGIOS_WARNING_TIME:
        nagios_status = "WARNING"
    return "EDGEMANAGE %s - %s" % (nagios_status, nagios_message)

def acquire_lock(lockfile):
    fp = open(lockfile, 'w')

    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        return False

    return True

def future_fetch(edgetest, testobject_host, testobject_path, testobject_proto):
    """Helper function to give us a return value that plays nice with as_completed"""

    fetch_result = edgetest.fetch(testobject_host, testobject_path, testobject_proto)
    return {edgetest.edgename: fetch_result}

def main(dnet, dry_run, verbose, do_nagios_output, config, state_obj):

    time_now = time.time()
    if state_obj.last_run and not dry_run and int(state_obj.last_run) + 59 > int(time_now):
        logging.error("Can't run - last run was %d, current time is %d",
                      state_obj.last_run, time_now)
        sys.exit(1)

    # Read the edgelist as a flat file
    # TODO have the option to check the file for YAML and then default to
    # flat list.
    with open(os.path.join(config["edgelist_dir"], dnet)) as edge_f:
        edge_list = [ i for i in edge_f.read().split("\n") if i.strip() ]
    if verbose:
        logging.info("Edge list is %s", str(edge_list))

    testobject_proto = config["testobject"]["proto"]
    testobject_host = config["testobject"]["host"]
    testobject_path = config["testobject"]["uri"]

    # Hash the local copy of the object to be requested from the edges
    with open(config["testobject"]["local"]) as test_local_f:
        testobject_hash = hashlib.md5(test_local_f.read()).hexdigest()
        logging.info("Hash of local object %s is %s" % (config["testobject"]["local"],
                                                        testobject_hash))

    edgescore_futures = []

    with ProcessPoolExecutor() as executor:
        for edgename in edge_list:
            edge_t = EdgeTest(edgename, testobject_hash)
            edgescore_futures.append(executor.submit(future_fetch,
                                                     edge_t, testobject_host,
                                                     testobject_path,
                                                     testobject_proto))

    decision = DecisionMaker()

    for f in as_completed(edgescore_futures):
        try:
            result = f.result()
        except Exception as e:
            # Do some shit here
            raise
        edge, value = result.items()[0]
        stat_store = StatStore(edge, config["healthdata_store"], nowrite=dry_run)
        stat_store.add_value(value)
        logging.info("Fetch time for %s: %f avg: %f" % (edge, value, stat_store.current_average()))

        decision.add_stat_store(stat_store)
    decision.check_threshold(config["goodenough"])

    if do_nagios_output:
        print nagios_output(state_obj.last_rotation())

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Manage Deflect edge status.')
    parser.add_argument("--dnet", "-A", dest="dnet", action="store",
                        help="Specify DNET (mandatory)")
    parser.add_argument("--config", "-c", dest="config_path", action="store",
                        help="Path to configuration file (defaults to %s)" % const.CONFIG_PATH,
                        default=const.CONFIG_PATH)
    parser.add_argument("--nagios", "-N", dest="nagios", action="store_true",
                        help="Nagios-friendly output", default=False)
    parser.add_argument("--dry-run", "-n", dest="dryrun", action="store_true",
                        help="Dry run - don't generate any files", default=False)
    parser.add_argument("--verbose", "-v", dest="verbose", action="store_true",
                        help="Verbose output", default=False)
    args = parser.parse_args()

    with open(args.config_path) as config_f:
        config = yaml.safe_load(config_f.read())

    logger = logging.getLogger()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler() # log to STDERR
        handler.setFormatter(
            logging.Formatter('edgemanage [%(process)d] %(levelname)s %(message)s')
        )
        logger.addHandler(handler)

    logging.debug("Command line options are %s", str(args))
    logging.debug("Full configuration is:\n %s", pprint.pformat(config))

    if not args.dnet:
        raise AttributeError("DNET is a mandatory option")

    state = StateFile()
    if os.path.exists(config["statefile"]):
        with open(config["statefile"]) as statefile_f:
            state = StateFile(json.loads(statefile_f.read()))

    if not acquire_lock(config["lockfile"]):
        raise Exception("Couldn't acquire lock file - is Edgemanage running elsewhere?")
    else:
        main(args.dnet, args.dryrun, args.verbose, args.nagios, config, state)
    state.set_last_run()
    if not args.dryrun:
        with open(config["statefile"], "w") as statefile_f:
            statefile_f.write(state.to_json())
