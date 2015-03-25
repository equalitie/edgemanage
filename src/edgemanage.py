#!/usr/bin/env python

from edgemanage import const, EdgeTest, StatStore, DecisionMaker, StateFile, EdgeList

import json
import glob
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

    return list(set(still_healthy))

def nagios_output(lastrotation):
    time_now = time.time()
    nagios_status = "OK"
    if lastrotation:
        nagios_message = "Last rotation was %ds ago" % (time_now - lastrotation)
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
    with open(os.path.join(config["edgelist_dir"], dnet)) as edge_f:
        edge_list = [ i for i in edge_f.read().split("\n") if i.strip() and not i.startswith("#") ]
    if verbose:
        logging.info("Edge list is %s", str(edge_list))

    testobject_proto = config["testobject"]["proto"]
    testobject_host = config["testobject"]["host"]
    testobject_path = config["testobject"]["uri"]

    # Hash the local copy of the object to be requested from the edges
    with open(config["testobject"]["local"]) as test_local_f:
        testobject_hash = hashlib.md5(test_local_f.read()).hexdigest()
        logging.info("Hash of local object %s is %s",
                     config["testobject"]["local"], testobject_hash)

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
        logging.info("Fetch time for %s: %f avg: %f",
                     edge, value, stat_store.current_average())
        decision.add_stat_store(stat_store)
    threshold_stats = decision.check_threshold(config["goodenough"])
    logging.debug("Stats of threshold check are %s", str(threshold_stats))

    # List of edges that will be made live
    live_edge_list = []
    edgelist = EdgeList()

    # Do we have a previous edge list?
    still_healthy_from_last_run = check_last_live(state_obj, decision)
    if still_healthy_from_last_run:
        logging.info("Got list of previously in use edges that are in a passing state: %s",
                     still_healthy_from_last_run)

    for still_healthy in still_healthy_from_last_run:
        edgelist.add_edge(still_healthy, state="pass", live=True)
    logging.debug("List of surviving passing edges is %s", edgelist.get_edges("pass"))

    if len(still_healthy_from_last_run) == config["edge_count"]:
        logging.info(
            "Old edge list is still healthy - not making any changes: %s",
            still_healthy_from_last_run
        )
    else:
        logging.debug(("Didn't have enough healthy edges from last run to meet "
                      "edge count - trying to add more edges"))

        for decision_edge, edge_state in decision.current_judgement.iteritems():
            edgelist.add_edge(decision_edge, state=edge_state)
        logging.debug("List of new and old passing edges is %s", edgelist.get_edges("pass"))

        if len(edgelist.get_edges("pass")) < config["edge_count"]:
            logging.warning(("Don't have enough passing edges to supply a full "
                             "list! (%d in pass state, %d healthy from last run)"),
                            config["edge_count"], len(edgelist.get_edges("pass")))


        # Attempt to meet demand, first with passing, then with
        # window, then with average passing
        for state in ["pass", "pass_window", "pass_average"]:
            filled_by_current_state = edgelist.set_live_by_state(state, config["edge_count"])
            if filled_by_current_state:
                logging.info("Filled requirement for %d edges with edges in state %s", config["edge_count"], state)
                break
        else:
            # Entering an "else" in the context of a "for" loop means
            # "we didn't break". It's horrible but it's exactly what
            # we need here.
            logging.error("Tried to add edges from all acceptable states but failed")
            # TODO randomly try to add edges in a panic

    if edgelist.get_live_count() == config["edge_count"]:
        logging.info("Successfully established %d edges: %s",
                     edgelist.get_live_count(), edgelist.get_live_edges())

        # Iterate over every *zone file in the zonetemplate dir and write out files.
        for zonefile in glob.glob("%s/*.zone" % config["zonetemplate_dir"]):
            zone_name = zonefile.split(".zone")[0].split("/")[-1]
            complete_zone_str = edgelist.generate_zone(
                zone_name, config["zonetemplate_dir"], config["dns"]
            )

            complete_zone_path = os.path.join(config["named_dir"], "%s.zone" % zone_name)
            #TODO add rotation of old files
            if not dry_run:
                with open(complete_zone_path, "w") as complete_zone_f:
                    logging.debug("Writing completed zone file for %s to %s",
                                  zone_name, complete_zone_path)
                    complete_zone_f.write(complete_zone_str)
            else:
                logging.debug(("In dry run so not writing file %s for zone %s. "
                               "It would have contained:\n%s"),
                              complete_zone_path, zone_name, complete_zone_str)

        if edgelist.get_live_edges() != state_obj.last_live:
            state_obj.add_rotation(const.STATE_HISTORICAL_ROTATIONS)
        state_obj.last_live = edgelist.get_live_edges()
    else:
        logging.error("Couldn't establish full edge list! Only have %d edges (%s), need %d",
                      edgelist.get_live_count(), edgelist.get_live_edges(), config["edge_count"])
        state_obj.add_rotation(const.STATE_HISTORICAL_ROTATIONS)
        state_obj.last_live = edgelist.get_live_edges()

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
