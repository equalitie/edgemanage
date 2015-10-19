#!/usr/bin/env python

from edgetest import EdgeTest, VerifyFailed, FetchFailed
from edgestate import EdgeState
from decisionmaker import DecisionMaker
from edgelist import EdgeList
from const import FETCH_TIMEOUT

from concurrent.futures import ProcessPoolExecutor, as_completed
import glob
import traceback
import hashlib
import logging
import os


def future_fetch(edgetest, testobject_host, testobject_path,
                 testobject_proto, testobject_verify):
    """Helper function to give us a return value that plays nice with as_completed"""

    fetch_status = None
    try:
        fetch_result = edgetest.fetch(testobject_host, testobject_path,
                                      testobject_proto, testobject_verify)
    except VerifyFailed as exc:
        # Ensure that we don't use hosts where verification has failed
        fetch_result = FETCH_TIMEOUT
        fetch_status = "verify_failed"
    except FetchFailed as exc:
        # Ensure that we don't use hosts where fetching the object has
        # caused a HTTP error
        fetch_result = FETCH_TIMEOUT
        fetch_status = "fetch_failed"
    except Exception as exc:
        logging.error("Uncaught exception in fetch! %s", traceback.format_exc())
    return {edgetest.edgename: (fetch_result, fetch_status)}


class EdgeManage(object):

    def _init_objects(self):
        # List of edges that will be made live
        self.edgelist_obj = EdgeList()
        # Object we will use to make a decision about edge liveness based
        # on the stat stores
        self.decision = DecisionMaker()

        self.edge_states = {}

        self.testobject_hash = self.get_testobject_hash()
        self.current_mtimes = self.zone_mtime_setup()

    def get_testobject_hash(self):
        # Hash the local copy of the object to be requested from the edges
        with open(self.config["testobject"]["local"]) as test_local_f:
            testobject_hash = hashlib.md5(test_local_f.read()).hexdigest()
            logging.info("Hash of local object %s is %s",
                         self.config["testobject"]["local"], testobject_hash)

        return testobject_hash

    def __init__(self, dnet, config, state, dry_run=False):
        '''
         Upper-level edgemanage object that is used to create
        lower-level edgemanage objects and accomplish the overall task
        of edge testing, rotation and zone file writing.

        '''

        self.dnet = dnet
        self.dry_run = dry_run
        self.config = config
        self.state_obj = state

        self._init_objects()

    def zone_mtime_setup(self):
        # Get a complete list of zone names
        current_mtimes = {}
        for zonefile in glob.glob("%s/%s/*.zone" % (self.config["zonetemplate_dir"], self.dnet)):
            zone_name = zonefile.split(".zone")[0].split("/")[-1]
            # And while we're here, let's get their mtimes
            current_mtime = int(os.stat(zonefile).st_mtime)
            current_mtimes[zone_name] = current_mtime
        return current_mtimes

    def add_edge_state(self, edge, edge_healthdata_path, nowrite=False):
        edge_state = EdgeState(edge, edge_healthdata_path, nowrite=nowrite)
        self.edge_states[edge] = edge_state

    def do_edge_tests(self):

        test_dict = self.config["testobject"]
        test_host = test_dict["host"]
        test_path = test_dict["uri"]
        test_proto = test_dict["proto"]
        test_verify = test_dict["verify"]

        edgescore_futures = []
        with ProcessPoolExecutor() as executor:
            for edgename in self.edge_states:
                edge_t = EdgeTest(edgename, self.testobject_hash)
                edgescore_futures.append(executor.submit(future_fetch,
                                                         edge_t, test_host,
                                                         test_path,
                                                         test_proto,
                                                         test_verify))

        verification_failues = []

        for f in as_completed(edgescore_futures):
            try:
                result = f.result()
            except Exception as e:
                # Do some shit here
                raise
            edge, value = result.items()[0]
            fetch_result, fetch_status = value

            if fetch_status == "verify_failed":
                verification_failues.append(edge)

            self.edge_states[edge].add_value(fetch_result)
            logging.info("Fetch time for %s: %f avg: %f",
                         edge, fetch_result,
                         self.edge_states[edge].current_average())

            # Skip edges that we have forced out of commission
            if self.edge_states[edge].mode == "unavailable":
                logging.debug("Skipping edge %s as its status has been set to unavailable", edge)
            else:
                # otherwise add it to the decision maker
                self.decision.add_edge_state(self.edge_states[edge])

        return verification_failues

    def check_last_live(self):

        # A list of edges that were in use last time that are still
        # healthy now.
        still_healthy = []

        if self.state_obj.last_live:
            logging.debug("Live edge list from previous run is %s",
                          self.state_obj.last_live)

        # Make sure that any edges that were in rotation are still
        # in a passing state. Discard any that are failing checks.
        for oldlive_edge in self.state_obj.last_live:
            if oldlive_edge in self.decision.current_judgement and \
               self.decision.get_judgement(oldlive_edge) == "pass":
                still_healthy.append(oldlive_edge)
            elif oldlive_edge not in self.decision.current_judgement:
                logging.warning(("Discarding previously live edge %s "
                                 "because it is no longer being checked",),
                                oldlive_edge)
            else:
                logging.debug(
                    "Discarding previously live edge %s because it is in state %s",
                    oldlive_edge,
                    self.decision.current_judgement[oldlive_edge])

        return list(set(still_healthy))

    def make_edges_live(self, force_update):

        # Returns true if any changes were made.

        good_enough = self.config["goodenough"]
        required_edge_count = self.config["edge_count"]
        if self.dnet in self.config["dnet_edge_count"]:
            required_edge_count = self.config["dnet_edge_count"][self.dnet]

        # Has the edgelist changed since last iteration?
        edgelist_changed = None
        # Have ANY changes happened since last iteration? Including zone
        # updates.
        any_changes = False

        threshold_stats = self.decision.check_threshold(good_enough)

        # Get the list of previously healthy edges
        still_healthy_from_last_run = self.check_last_live()

        for edgename, edge_state in self.edge_states.iteritems():
            if edge_state.mode == "force":
                if self.decision.get_judgement(edgename) == "pass":
                    logging.debug(
                        "Making host %s live because it is in mode force and it is in state pass",
                        edgename)

                    # Don't set edgelist_changed to True if we're
                    # already heathy and live
                    if not edgename in still_healthy_from_last_run:
                        self.edgelist_obj.add_edge(edgename, state="pass", live=True)
                        edgelist_changed = True

            elif edge_state.mode == "blindforce":
                logging.debug("Making host %s live because it is in mode blindforce.",
                              edgename)
                self.edgelist_obj.add_edge(edgename, state="pass", live=True)

                # Don't update the edgelist if we're still in the last
                # live list. We don't care if we're healthy.
                if edgename not in self.state_obj.last_live:
                    edgelist_changed = True

        logging.debug("Stats of threshold check are %s", str(threshold_stats))

        # If everything is still healthy from the last run then use those.
        if still_healthy_from_last_run:
            logging.info("Got list of previously in use edges that are in a passing state: %s",
                         still_healthy_from_last_run)
            if edgelist_changed == None:
                # This check is to ensure that a previously-passing
                # list doesn't ignore forced or blindforced edges.
                edgelist_changed = False

        for still_healthy in still_healthy_from_last_run:
            if len(self.edgelist_obj) < required_edge_count:
                self.edgelist_obj.add_edge(still_healthy, state="pass", live=True)

        if len(still_healthy_from_last_run) == required_edge_count:
            logging.info(
                "Old edge list is still healthy - not making any changes"
            )
        else:
            logging.debug(("Didn't have enough healthy edges from last run to meet "
                           "edge count - trying to add more edges"))
            edgelist_changed = True

            for decision_edge, edge_state in self.decision.current_judgement.iteritems():
                if decision_edge not in self.edgelist_obj.edges:
                    self.edgelist_obj.add_edge(decision_edge, state=edge_state)
            logging.debug("List of previously passing edges is currently %s",
                          self.edgelist_obj.get_live_edges())

            # Attempt to meet demand, first with passing, then with
            # window, then with average passing
            for desired_state in ["pass", "pass_window", "pass_average"]:
                filled_by_current_state = self.edgelist_obj.set_live_by_state(desired_state,
                                                                              required_edge_count)
                if filled_by_current_state:
                    logging.info("Filled requirement for %d edges with edges in state %s",
                                 required_edge_count, desired_state)
                    break
            else:
                # Entering an "else" in the context of a "for" loop means
                # "we didn't break". It's horrible but it's exactly what
                # we need here.
                logging.error("Tried to add edges from all acceptable states but failed")
                # TODO randomly try to add edges in a panic

        if self.edgelist_obj.get_live_count() == required_edge_count:
            logging.info("Successfully established %d edges: %s",
                         self.edgelist_obj.get_live_count(),
                         self.edgelist_obj.get_live_edges())

            # Iterate over every *zone file in the zonetemplate dir and write out files.
            for zone_name in self.current_mtimes:

                # Unless an update is forced:
                # * Skip files that haven't been changed
                # * Write out zone files we haven't seen before
                # * don't write out updated zone files when we aren't changing edge list
                old_mtime = self.state_obj.zone_mtimes.get(zone_name)
                if not force_update and not edgelist_changed and old_mtime and old_mtime == self.current_mtimes[zone_name]:
                    logging.info("Not writing zonefile for %s because there are no changes pending",
                                 zone_name)
                    continue
                else:
                    any_changes = True

                complete_zone_str = self.edgelist_obj.generate_zone(
                    zone_name, os.path.join(self.config["zonetemplate_dir"], self.dnet),
                    self.config["dns"]
                )

                complete_zone_path = os.path.join(self.config["named_dir"],
                                                  "%s.zone" % zone_name)
                #TODO add rotation of old files
                if not self.dry_run:
                    with open(complete_zone_path, "w") as complete_zone_f:
                        logging.debug("Writing completed zone file for %s to %s",
                                      zone_name, complete_zone_path)
                        complete_zone_f.write(complete_zone_str)
                else:
                    logging.debug(("In dry run so not writing file %s for zone %s. "
                                   "It would have contained:\n%s"),
                                  complete_zone_path, zone_name, complete_zone_str)


        else:
            logging.error("Couldn't establish full edge list! Only have %d edges (%s), need %d",
                          self.edgelist_obj.get_live_count(),
                          self.edgelist_obj.get_live_edges(),
                          required_edge_count)

        # We've got our edges, one way or another - let's set their states
        # Note in the statefile that this edge has been put into rotation
        for edge in self.edge_states:

            if self.edgelist_obj.is_live(edge):
                # Note in the statefile that this edge has been put into rotation
                logging.debug("Setting edge %s to state in", edge)
                self.edge_states[edge].add_rotation()
                self.edge_states[edge].set_state("in")
            else:
                logging.debug("Setting edge %s to state out", edge)
                self.edge_states[edge].set_state("out")

            if self.edge_states[edge].mode != "unavailable":
                current_health = self.decision.get_judgement(edge)
                self.edge_states[edge].set_health(current_health)

        self.state_obj.zone_mtimes = self.current_mtimes

        return any_changes or edgelist_changed
