from const import DECISION_SLICE_WINDOW

import logging
import time

JUDGEMENT = {
    # Last fetch is under threshold
    "under_threshold": None,
    # Last DECISION_SLICE_WINDOW fetches averaged under the threshold
    "slice_under_threshold": None,
    # The average of all FETCH_HISTORY fetches were under the
    # threshold
    "average_under_thresold": None,
}

class DecisionMaker(object):

    def __init__(self):
        self.stat_stores = {}
        self.current_judgement = {}

    def add_stat_store(self, stat_store):
        self.stat_stores[stat_store.edgename] = stat_store
        self.current_judgement[stat_store.edgename] = JUDGEMENT.copy()

    def check_threshold(self, good_enough):
        print self.stat_stores.keys()
        for edgename, stat_store in self.stat_stores.iteritems():
            time_slice = stat_store[time.time() - DECISION_SLICE_WINDOW:time.time()]
            time_slice_avg = sum(time_slice)/len(time_slice)
            if stat_store.last_value() < good_enough:
                logging.info("PASS: Last fetch for %s is under the threshold (%f < %f)", edgename,
                             stat_store.last_value(), good_enough)
            elif time_slice_avg < good_enough:
                logging.info("UNSURE: Last fetch for %s is NOT under the threshold but the average of the last %d items is (%f < %f)", edgename, len(time_slice), time_slice_avg, good_enough)
            # TODO check a slice of dates for a given period here - total average is not good enough
            elif stat_store.current_average() < good_enough:
                logging.info("UNSURE: Last fetch for %s is NOT under the threshold but under the average (%f < %f)",
                             edgename, stat_store.current_average(), good_enough)
            else:
                logging.info("FAIL: No check for %s has passed - last fetch time was %f", edgename, stat_store.last_value())
