#!/usr/bin/env python

from __future__ import absolute_import
from .edgetest import EdgeTest, VerifyFailed, FetchFailed
from .edgestate import EdgeState
from .decisionmaker import DecisionMaker
from .edgelist import EdgeList
from . import const

from concurrent.futures import ThreadPoolExecutor, as_completed, CancelledError
import itertools
import glob
import traceback
import hashlib
import logging
import os
import six


def future_fetch(edgetest, testobject_host, testobject_path,
                 testobject_proto, testobject_port, testobject_verify):
    """Helper function to give us a return value that plays nice with as_completed"""

    fetch_status = None
    try:
        fetch_result = edgetest.fetch(testobject_host, testobject_path,
                                      testobject_proto, testobject_port,
                                      testobject_verify)
    except VerifyFailed:
        # Ensure that we don't use hosts where verification has failed
        fetch_result = const.FETCH_TIMEOUT
        fetch_status = "verify_failed"
    except FetchFailed:
        # Ensure that we don't use hosts where fetching the object has
        # caused a HTTP error
        fetch_result = const.FETCH_TIMEOUT
        fetch_status = "fetch_failed"
    except Exception:
        logging.error("Uncaught exception in fetch! %s", traceback.format_exc())
    return {edgetest.edgename: (fetch_result, fetch_status)}


class EdgeManage(object):

    def _init_objects(self):
        # List of edges that will be made live
        self.edgelist_obj = EdgeList()
        # Object we will use to make a decision about edge liveness based
        # on the stat stores
        self.decision = DecisionMaker()
        self.canary_decision = None

        if self.canary_data:
            # Because we treat the behaviour of canaries differently
            # let's ringfence them here.
            self.canary_decision = DecisionMaker()

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

    def __init__(self, dnet, config, state, canary_data={}, dry_run=False):
        '''
         Upper-level edgemanage object that is used to create
        lower-level edgemanage objects and accomplish the overall task
        of edge testing, rotation and zone file writing.

        Args:
         dnet: string representing the dnet for which we're writing rules
         config: configuration dictionary
         state: state object
         canary_data: per-site canary site->canary_ip dict

        '''

        self.dnet = dnet
        self.dry_run = dry_run
        self.config = config
        self.state_obj = state

        self.canary_data = canary_data

        self._init_objects()

    def zone_mtime_setup(self):
        # Get a complete list of zone names
        current_mtimes = {}
        for zonefile in glob.glob("%s/%s/*.zone" % (self.config["zonetemplate_dir"], self.dnet)):
            zone_name = zonefile.rsplit(".zone", 1)[0].split("/")[-1]
            # And while we're here, let's get their mtimes
            current_mtime = int(os.stat(zonefile).st_mtime)
            current_mtimes[zone_name] = current_mtime
        return current_mtimes

    def add_edge_state(self, edge, edge_healthdata_path, nowrite=False):
        try:
            edge_state = EdgeState(edge, edge_healthdata_path, nowrite=nowrite)
        except ValueError as exc:
            logging.error("Failed to load edgestate file for %s: %s", edge, str(exc))

            return False
        self.edge_states[edge] = edge_state
        return True

    def check_canary_kill_treshhold(self, canary_futures):
        """
        Cancel canary tests and disable all canaries if too many are failing.

        All canary tests which have not run already are canceled and their
        result time will be set to the FETCH_TIMEOUT value. All finished
        canary tests will be failed in DecisionMaker when `edges_disabled` is True.
        """
        canary_stats = self.canary_decision.check_threshold(self.config["goodenough"])

        # Cancel all queued canary tests when too many canaries have failed.
        if canary_stats["fail"] >= self.config["canary_killer"]:
            self.canary_decision.edges_disabled = True

            cancelled = [future.cancel() for future in canary_futures]
            logging.info("Hit canary kill limit! canceled %d / %d queued canary tests.",
                         cancelled.count(True), len(cancelled))

            # Set every untested canary as TIMEOUT when we disable them.
            for untested_edge in [edge for edge in self.canary_data.values() if
                                  edge not in self.canary_decision.edge_states]:
                self.edge_states[untested_edge].add_value(const.FETCH_TIMEOUT)
                self.canary_decision.add_edge_state(self.edge_states[untested_edge])

    def do_edge_tests(self):
        test_dict = self.config["testobject"]
        test_host = test_dict["host"]
        test_path = test_dict["uri"]
        test_proto = test_dict["proto"]
        test_port = test_dict.get("port", 80)
        test_verify = test_dict["verify"]
        if self.config.get("testing"):
            # Allow FETCH_TIMEOUT to be overridden in TESTING mode.
            const.FETCH_TIMEOUT = self.config.get("timeout") or const.FETCH_TIMEOUT

        edgescore_futures = []
        canary_futures = []
        verification_failues = []
        with ThreadPoolExecutor(max_workers=self.config["workers"]) as executor:
            for edgename in self.edge_states:
                # Send raw IP as the host header when in the testing environment
                if self.config.get("testing"):
                    test_host = edgename

                edge_t = EdgeTest(edgename, self.testobject_hash)
                edgetest_future = executor.submit(future_fetch,
                                                  edge_t, test_host,
                                                  test_path,
                                                  test_proto,
                                                  test_port,
                                                  test_verify)

                # Check if the current edge is a canary edge
                if edgename not in list(self.canary_data.values()):
                    edgescore_futures.append(edgetest_future)
                else:
                    canary_futures.append(edgetest_future)

            # Iterate over the results of both Futures lists
            for f in as_completed(itertools.chain(edgescore_futures, canary_futures)):
                try:
                    result = f.result()
                except CancelledError:
                    # Do not try and process canceled edge tests
                    continue

                edge, value = list(result.items())[0]
                fetch_result, fetch_status = value

                if fetch_status == "verify_failed":
                    verification_failues.append(edge)

                # The edge will not be in the edge_states list if it's statefile is not parsable.
                # We should skip it and provide a warning so as to avoid stalling edgemanage.
                if edge not in self.edge_states:
                    logging.error("Could not find edge data for %s. Is the edge state "
                                  "file corrupt?", edge)
                    continue

                self.edge_states[edge].add_value(fetch_result)
                logging.info("Fetch time for %s: %f avg: %f",
                             edge, fetch_result,
                             self.edge_states[edge].current_average())

                # Skip edges that we have forced out of commission
                if self.edge_states[edge].mode == "unavailable":
                    logging.debug("Skipping edge %s as its status has been set to unavailable",
                                  edge)
                else:
                    # otherwise add it to the appropriate decision maker
                    if edge in list(self.canary_data.values()):
                        self.canary_decision.add_edge_state(self.edge_states[edge])
                    elif edge in self.edge_states:
                        self.decision.add_edge_state(self.edge_states[edge])

                # Hard-kill the remaining canary tests if too many are failing. This
                # also disables any canaries which have already been successfully tested.
                if self.canary_data:
                    if self.config["canary_killer"] and not self.canary_decision.edges_disabled:
                        self.check_canary_kill_treshhold(canary_futures)

        return verification_failues

    def check_last_live(self):
        """
        A list of edges that were in use last time that are still
        healthy now.

        Healthy means the fetch time is less than the good_enough threshold
        """
        still_healthy = []

        if self.state_obj.last_live:
            logging.debug("Live edge list from previous run is %s",
                          self.state_obj.last_live)

        # Make sure that any edges that were in rotation are still
        # in a passing state. Discard any that are failing checks.
        for oldlive_edge in self.state_obj.last_live:

            try:
                if oldlive_edge in self.canary_data:
                    oldlive_health = self.canary_decision.get_judgement(oldlive_edge)
                else:
                    oldlive_health = self.decision.get_judgement(oldlive_edge)
            except KeyError:
                oldlive_health = None

            if (oldlive_edge in self.decision.current_judgement and
                    oldlive_health == "pass_threshold"):
                still_healthy.append(oldlive_edge)
            elif oldlive_edge not in self.decision.current_judgement:
                logging.warning(("Discarding previously live edge %s "
                                 "because it is no longer being checked",),
                                oldlive_edge)
            else:
                logging.debug(
                    "Discarding previously live edge %s because it is not "
                    "in state 'pass_threshold', current state: %s",
                    oldlive_edge,
                    self.decision.get_judgement(oldlive_edge))

        return list(set(still_healthy))

    def get_fastest_edges_by_state(self, edge_list, state, desired_count):
        """
        Get the top `desired_count` fastest edges with the specified state
        """
        edges_in_state = [edge for edge in edge_list
                          if self.decision.get_judgement(edge) == state]

        # Sort the list of edges with specified state
        edge_list = sorted(edges_in_state,
                           key=lambda edge: self.decision.edge_average(edge))

        logging.debug("Sorted %s edges: %s", state, edge_list)

        choosen_edges = []
        for edge in edge_list:
            if len(choosen_edges) == desired_count:
                logging.debug("Edgemanage got enough (%d) edges in state %s",
                              desired_count, state)
                break
            choosen_edges.append(edge)
        return choosen_edges

    def make_edges_live(self, force_update):

        '''
        Choose edges, write out zone files and state info.

        Args:
         force_update: write out renewed zone files even if no changes needed

        '''
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

        if self.canary_decision:
            canary_stats = self.canary_decision.check_threshold(good_enough)
            logging.debug("Stats of canary threshold check are %s", str(canary_stats))

        # Get the list of edges that were 'in' (live) the last time and are
        # still healthy (under the good_enough threshold)
        still_healthy_from_last_run = self.check_last_live()

        for edgename, edge_state in six.iteritems(self.edge_states):
            if edgename not in list(self.canary_data.values()) and edge_state.mode == "force":
                if self.decision.edge_is_passing(edgename):
                    logging.debug(
                        "Making host %s live because it is in mode force and it is in state pass",
                        edgename)

                    # Don't set edgelist_changed to True if we're
                    # already healthy and live
                    if edgename not in still_healthy_from_last_run:
                        self.edgelist_obj.add_edge(edgename, state="pass", live=True)
                        edgelist_changed = True

            elif edgename not in list(self.canary_data.values()) and edge_state.mode == "blindforce":
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
            if edgelist_changed is None:
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

            # This loops over the non-canary edges
            remaining_edges = []
            for decision_edge, edge_state in six.iteritems(self.decision.current_judgement):
                if decision_edge not in self.edgelist_obj.edges:
                    remaining_edges.append(decision_edge)

            logging.debug("List of previously passing edges is currently %s",
                          self.edgelist_obj.get_live_edges())

            # Attempt to meet demand starting with the most responsive edge states
            for desired_state in ["pass_threshold", "pass_window", "pass_average", "pass"]:
                needed_edges = required_edge_count - self.edgelist_obj.get_live_count()
                filled_by_current_state = self.get_fastest_edges_by_state(remaining_edges,
                                                                          desired_state,
                                                                          needed_edges)
                for edge in filled_by_current_state:
                    self.edgelist_obj.add_edge(edge, state=desired_state, live=True)

                if self.edgelist_obj.get_live_count() == required_edge_count:
                    logging.info("Filled requirement for %d edges with edges in state %s",
                                 required_edge_count, desired_state)
                    break
            else:
                # Entering an "else" in the context of a "for" loop means
                # "we didn't break". It's horrible but it's exactly what
                # we need here.
                logging.error("Tried to add edges from all acceptable states but failed")

                # As a last option we add use the last live set of edges, even if
                # they are unresponsive. This isn't a great option, but it's better
                # than sending an empty set of edges to the DNS servers.
                logging.error("Re-adding the last live edges, even though they are failing!")
                for edgename in self.state_obj.last_live:
                    self.edgelist_obj.add_edge(edgename, state="pass", live=True)
                edgelist_changed = False

        if self.edgelist_obj.get_live_count() == required_edge_count:
            logging.info("Successfully established %d edges: %s",
                         self.edgelist_obj.get_live_count(),
                         self.edgelist_obj.get_live_edges())

            # Iterate over every *zone file in the zonetemplate dir and write out files.
            # (current_mtimes is an array that associates a zone name to its
            # mtime)
            for zone_name in self.current_mtimes:

                previous_canary = None
                if zone_name in self.state_obj.active_canaries:
                    previous_canary = self.state_obj.active_canaries[zone_name]

                canary_changed = False
                canary_edge = None
                if zone_name in self.canary_data:
                    # We have a canary edge configured, let's see if
                    # it's healthy
                    canary_ip = self.canary_data[zone_name]
                    try:
                        canary_health = self.canary_decision.get_judgement(canary_ip)
                    except KeyError:
                        # Mark canary as missing if a judgement can't be found for the
                        # canary edge IP.
                        canary_health = "missing"

                    if canary_health == "pass" or canary_health == "pass_window":
                        logging.info("Zone %s has a canary edge configured: %s",
                                     zone_name, canary_ip)
                        canary_edge = canary_ip
                    else:
                        logging.info(
                            ("Zone %s has %s configued as a canary but it is "
                             "in state %s so it will not be used. "),
                            zone_name, canary_ip, canary_health)

                    # Is the canary different from the one used before?
                    # Will we need to re-write zonefile?
                    if not previous_canary and canary_edge:
                        logging.info("Canary edge %s for zone %s is new: re-writing zonefile",
                                     canary_edge, zone_name)
                        canary_changed = True
                    elif not canary_edge and previous_canary:
                        logging.info("Canary edge %s for zone %s not used anymore: re-writing "
                                     "zonefile", previous_canary, zone_name)
                        canary_changed = True
                    elif canary_edge != previous_canary:
                        logging.info("Canary edge for zone %s changed from %s to %s: re-writing "
                                     "zonefile", zone_name, previous_canary, canary_edge)
                        canary_changed = True

                elif previous_canary:
                    # We used to have a canary for the domain, but it is not
                    # configured anymore: we'll just need to re-write zonefile
                    logging.info("Canary edge %s for zone %s not used anymore: re-writing "
                                 "zonefile", previous_canary, zone_name)
                    canary_changed = True

                if canary_edge:
                    self.state_obj.active_canaries[zone_name] = canary_edge
                elif previous_canary:
                    del(self.state_obj.active_canaries[zone_name])

                # Unless an update is forced:
                # * Skip files that haven't been changed
                # * Write out zone files we haven't seen before
                # * don't write out updated zone files when we aren't changing edge list
                old_mtime = self.state_obj.zone_mtimes.get(zone_name)
                if (not force_update and not edgelist_changed and not canary_changed and
                        old_mtime and old_mtime == self.current_mtimes[zone_name]):
                    logging.info("Not writing zonefile for %s because there are no changes pending",
                                 zone_name)
                    continue
                else:
                    any_changes = True

                complete_zone_str = self.edgelist_obj.generate_zone(
                    zone_name, os.path.join(self.config["zonetemplate_dir"], self.dnet),
                    self.config["dns"], canary_edge=canary_edge
                )

                complete_zone_path = os.path.join(self.config["named_dir"],
                                                  "%s.zone" % zone_name)
                # TODO: add rotation of old files
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
            try:
                if edge in list(self.canary_data.values()):
                    is_canary = True
                    current_health = self.canary_decision.get_judgement(edge)
                else:
                    is_canary = False
                    current_health = self.decision.get_judgement(edge)

                self.edge_states[edge].set_health(current_health)
            except KeyError:
                logging.debug("Could not get health judgement for edge %s", edge)

            if is_canary is False:
                if self.edgelist_obj.is_live(edge):
                    # Note in the statefile that this edge has been put into rotation
                    logging.debug("Setting edge %s to state in", edge)
                    self.edge_states[edge].add_rotation()
                    self.edge_states[edge].set_state("in")
                else:
                    logging.debug("Setting edge %s to state out", edge)
                    self.edge_states[edge].set_state("out")
            else:
                # Canaries are silently set to "out", because the state "in" implies a
                # dnet-wise insertion, which doesn't make sense for canaries.
                # There should probably be another state defined for canaries?
                self.edge_states[edge].set_state("out")

        self.state_obj.zone_mtimes = self.current_mtimes

        return any_changes or edgelist_changed
