#!/usr/bin/env python

from edgemanage import const, EdgeTest, StatStore, DecisionMaker, StateFile, EdgeList

import json
import time
import os
import sys
import random
import yaml
import argparse
import logging
import hashlib
import fcntl
import pprint
from concurrent.futures import ProcessPoolExecutor, as_completed

# TODO Wrap these functions and most of main in an object - everything
# is messy as fuck.

def check_last_live(state_obj, decision_obj):

    # A list of edges that were in use last time that are still
    # healthy now.
    still_healthy = []

    if state_obj.last_live:
        logging.debug("Live edge list from previous run is %s", state_obj.last_live)

    # Make sure that any edges that were in rotation are still
    # in a passing state. Discard any that are failing checks.
    for oldlive_edge in state_obj.last_live:
        if oldlive_edge in decision_obj.current_judgement and \
           decision_obj.current_judgement[oldlive_edge] == "pass":
            still_healthy.append(oldlive_edge)
        else:
            logging.debug("Discarding previously live edge %s because it is in state %s",
                          oldlive_edge,
                          decision_obj.current_judgement[oldlive_edge])

    return still_healthy

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
    # Attempt to lock a file so that we don't have overlapping runs
    # Might be deperecated in future in favour of the time checking
    # used at the start of main()
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
    threshold_stats = decision.check_threshold(config["goodenough"])
    logging.debug("Stats of threshold check are %s", str(threshold_stats))

    # List of edges that will be made live
    live_edge_list = []

    # Do we have a previous edge list?
    still_healthy_from_last_run = check_last_live(state_obj, decision)
    if still_healthy_from_last_run:
        logging.info("Got list of previously in use edges that are in a passing state: %s",
                     still_healthy_from_last_run)

    if len(still_healthy_from_last_run) == config["edge_count"]:
        logging.info(
            "Old edge list is still healthy - not making any changes: %s",
            still_healthy_from_last_run
        )
        live_edge_list = still_healthy_from_last_run
    else:
        logging.debug(("Didn't have enough healthy edges from last run to meet "
                      "edge count - trying to add more edges"))

        current_pass_edges = [ i for i in decision.current_judgement if \
                               decision.current_judgement[i] == "pass" ]
        if len(current_pass_edges) < (config["edge_count"] - len(still_healthy_from_last_run)):
            logging.warning(("Don't have enough passing edges to supply a full "
                             "list! (%d in pass state, %d healthy from last run)"),
                            config["edge_count"], len(still_healthy_from_last_run))

        for pass_edge in current_pass_edges:
            if len(live_edge_list) == config["edge_count"]:
                # We have enough edges, stop adding edges
                break
            else:
                live_edge_list.append(current_pass_edges[
                    random.randrange(len(current_pass_edges))
                ])

    if len(live_edge_list) == config["edge_count"]:
        logging.info("Successfully established %d edges: %s",
                     len(live_edge_list), str(live_edge_list))


        edgelist = EdgeList()
        for edgename in live_edge_list:
            edgelist.add_edge(edgename)
        # TODO HACK TEST populate this from a file
        print edgelist.generate_zone("deflect.ca", config["zonetemplate_dir"], config["dns"])

        if sorted(live_edge_list) != sorted(state_obj.last_live):
            state_obj.add_rotation(const.STATE_HISTORICAL_ROTATIONS)
        state_obj.last_live = sorted(live_edge_list)
    else:
        logging.error("Couldn't establish full edge list! Only have %d edges (%s), need %d",
                      len(live_edge_list), str(live_edge_list), config["edge_count"])
        state_obj.add_rotation(const.STATE_HISTORICAL_ROTATIONS)
        state_obj.last_live = sorted(live_edge_list)



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
