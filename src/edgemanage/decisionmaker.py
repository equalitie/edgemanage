from const import DECISION_SLICE_WINDOW

import logging
import time

VALID_STATUSES = ["pass", "fail", "pass_window", "pass_average"]

class DecisionMaker(object):

    def __init__(self):
        self.stat_stores = {}
        # A results dict with edge as key, string as value, one of
        # VALID_STATUSES
        self.current_judgement = {}

    def add_stat_store(self, stat_store):
        self.stat_stores[stat_store.edgename] = stat_store
        self.current_judgement[stat_store.edgename] = None

    def check_threshold(self, good_enough):

        ''' Check fetch response times for being under the given
        threshold.

        '''

        # dict for stats to return
        results_dict = {}
        for statusname in VALID_STATUSES:
            results_dict[statusname] = 0

        for edgename, stat_store in self.stat_stores.iteritems():
            time_slice = stat_store[time.time() - DECISION_SLICE_WINDOW:time.time()]
            if time_slice:
                time_slice_avg = sum(time_slice)/len(time_slice)
                logging.debug("Analysing %s. Last val: %f, time slice: %f, average: %f",
                              edgename, stat_store.last_value(), time_slice_avg,
                              stat_store.current_average())
            else:
                time_slice_avg = None
                logging.debug("Analysing %s. Last val: %f, time slice: Not enough data, average: %f",
                              edgename, stat_store.last_value(), stat_store.current_average())

            if stat_store.last_value() < good_enough:
                logging.info("PASS: Last fetch for %s is under the threshold (%f < %f)", edgename,
                             stat_store.last_value(), good_enough)
                self.current_judgement[edgename] = "pass"
                results_dict["pass"] += 1
            elif time_slice and time_slice_avg < good_enough:
                self.current_judgement[edgename] = "pass_window"
                results_dict["pass_window"] += 1
                logging.info("UNSURE: Last fetch for %s is NOT under the threshold but the average of the last %d items is (%f < %f)", edgename, len(time_slice), time_slice_avg, good_enough)
            elif stat_store.current_average() < good_enough:
                results_dict["pass_average"] += 1
                self.current_judgement[edgename] = "pass_average"
                logging.info("UNSURE: Last fetch for %s is NOT under the threshold but under the average (%f < %f)",
                             edgename, stat_store.current_average(), good_enough)
            else:
                results_dict["fail"] += 1
                self.current_judgement[edgename] = "fail"
                logging.info("FAIL: No check for %s has passed - last fetch time was %f", edgename, stat_store.last_value())

        return results_dict
