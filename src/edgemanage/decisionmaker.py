from const import DECISION_SLICE_WINDOW, VALID_HEALTHS, FETCH_TIMEOUT

import logging
import time

class DecisionMaker(object):

    def __init__(self):
        self.edge_states = {}
        # A results dict with edge as key, string as value, one of
        # VALID_HEALTHS
        self.current_judgement = {}

    def add_edge_state(self, edge_state):
        self.edge_states[edge_state.edgename] = edge_state
        self.current_judgement[edge_state.edgename] = None

    def get_judgement(self, edgename):
        return self.current_judgement[edgename]

    def check_threshold(self, good_enough):

        ''' Check fetch response times for being under the given
        threshold.

        '''

        # dict for stats to return
        results_dict = {}
        for statusname in VALID_HEALTHS:
            results_dict[statusname] = 0

        for edgename, edge_state in self.edge_states.iteritems():
            time_slice = edge_state[time.time() - DECISION_SLICE_WINDOW:time.time()]
            if time_slice:
                time_slice_avg = sum(time_slice)/len(time_slice)
                logging.debug("Analysing %s. Last val: %f, time slice: %f, average: %f",
                              edgename, edge_state.last_value(), time_slice_avg,
                              edge_state.current_average())
            else:
                time_slice_avg = None
                logging.debug("Analysing %s. Last val: %f, time slice: Not enough data, average: %f",
                              edgename, edge_state.last_value(), edge_state.current_average())

            if edge_state.last_value() < good_enough:
                logging.info("PASS: Last fetch for %s is under the threshold (%f < %f)", edgename,
                             edge_state.last_value(), good_enough)
                self.current_judgement[edgename] = "pass"
                results_dict["pass"] += 1
            elif edge_state.last_value() == FETCH_TIMEOUT:
                results_dict["fail"] += 1
                self.current_judgement[edgename] = "fail"
                logging.info(("FAIL: Fetch time for %s is equal to the FETCH_TIMEOUT of %d. "
                              "Automatic fail"),
                             edgename, FETCH_TIMEOUT)
            elif time_slice and time_slice_avg < good_enough:
                self.current_judgement[edgename] = "pass_window"
                results_dict["pass_window"] += 1
                logging.info("UNSURE: Last fetch for %s is NOT under the threshold but the average of the last %d items is (%f < %f)", edgename, len(time_slice), time_slice_avg, good_enough)
            elif edge_state.current_average() < good_enough:
                results_dict["pass_average"] += 1
                self.current_judgement[edgename] = "pass_average"
                logging.info("UNSURE: Last fetch for %s is NOT under the threshold but under the average (%f < %f)",
                             edgename, edge_state.current_average(), good_enough)
            else:
                results_dict["fail"] += 1
                self.current_judgement[edgename] = "fail"
                logging.info("FAIL: No check for %s has passed - last fetch time was %f",
                             edgename, edge_state.last_value())

        return results_dict
