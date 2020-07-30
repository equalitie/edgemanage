from __future__ import absolute_import
from . import const

import logging
import time
import six


class DecisionMaker(object):

    def __init__(self):
        self.edge_states = {}
        # A results dict with edge as key, string as value, one of
        # VALID_HEALTHS
        self.current_judgement = {}
        self.edges_disabled = False

    def add_edge_state(self, edge_state):
        self.edge_states[edge_state.edgename] = edge_state
        self.current_judgement[edge_state.edgename] = None

    def get_judgement(self, edgename):
        return self.current_judgement[edgename]

    def edge_is_passing(self, edgename):
        return self.get_judgement(edgename) != "fail"

    def edge_average(self, edgename):
        return self.edge_states[edgename].current_average()

    def check_threshold(self, good_enough):

        ''' Check fetch response times for being under the given
        threshold.

        '''

        # dict for stats to return
        results_dict = {}
        for statusname in const.VALID_HEALTHS:
            results_dict[statusname] = 0

        # Set all as failed if this set of edges have been disabled
        if self.edges_disabled:
            for edgename in self.edge_states:
                results_dict["fail"] += 1
                self.current_judgement[edgename] = "fail"
            logging.info("FAIL: %d edges have been disabled", results_dict["fail"])
            return results_dict

        for edgename, edge_state in six.iteritems(self.edge_states):
            time_slice = edge_state[time.time() - const.DECISION_SLICE_WINDOW:time.time()]
            if time_slice:
                time_slice_avg = sum(time_slice)/len(time_slice)
                logging.debug("Analysing %s. Last val: %f, time slice: %f, average: %f",
                              edgename, edge_state.last_value(), time_slice_avg,
                              edge_state.current_average())
            else:
                time_slice_avg = None
                logging.debug("Analysing %s. Last val: %f, time slice: Not enough data, "
                              "average: %f",
                              edgename, edge_state.last_value(), edge_state.current_average())

            if edge_state.last_value() < good_enough:
                self.current_judgement[edgename] = "pass_threshold"
                results_dict["pass_threshold"] += 1
                logging.info("PASS: Last fetch for %s is under the good_enough threshold "
                             "(%f < %f)", edgename, edge_state.last_value(), good_enough)
            elif edge_state.last_value() == const.FETCH_TIMEOUT:
                # FETCH_TIMEOUT must be checked before the average measurements. An edge
                # whose most recent fetch has failed should be marked as fail even if
                # the average value is still passing.
                self.current_judgement[edgename] = "fail"
                results_dict["fail"] += 1
                logging.info(("FAIL: Fetch time for %s is equal to the FETCH_TIMEOUT of %d. "
                              "Automatic fail"),
                             edgename, const.FETCH_TIMEOUT)
            elif time_slice and time_slice_avg < good_enough:
                self.current_judgement[edgename] = "pass_window"
                results_dict["pass_window"] += 1
                logging.info("UNSURE: Last fetch for %s is NOT under the good_enough threshold "
                             "but the average of the last %d items is (%f < %f)",
                             edgename, len(time_slice), time_slice_avg, good_enough)
            elif edge_state.current_average() < good_enough:
                self.current_judgement[edgename] = "pass_average"
                results_dict["pass_average"] += 1
                logging.info("UNSURE: Last fetch for %s is NOT under the good_enough threshold "
                             "but under the average (%f < %f)",
                             edgename, edge_state.current_average(), good_enough)
            else:
                self.current_judgement[edgename] = "pass"
                results_dict["pass"] += 1
                logging.info("PASS: Last fetch for %s is not under the good_enough threshold "
                             "but is passing (%f < %f)", edgename,
                             edge_state.last_value(), const.FETCH_TIMEOUT)

        return results_dict
