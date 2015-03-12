import logging

JUDGEMENT = {
    "under_goodenough": None
}

class DecisionMaker(object):

    def __init__(self):
        self.stat_stores = {}
        self.current_judgement = {}

    def add_stat_store(self, stat_store):
        self.stat_stores[stat_store.edgename] = stat_store
        self.current_judgement[stat_store.edgename] = JUDGEMENT.copy()

    def check_threshold(self, good_enough):
        for edgename, stat_store in self.stat_stores.iteritems():
            if stat_store.last_value() < good_enough:
                logging.info("Last fetch for %s is under the threshold (%f < %f)", edgename,
                             stat_store.last_value(), good_enough)
            # TODO check a slice of dates for a given period here - total average is not good enough
            elif stat_store.current_average() < good_enough:
                logging.info("Last fetch for %s is NOT under the threshold but under the average (%f < %f)",
                             edgename, stat_store.current_average(), good_enough)
            else:
                logging.info("No check for %s has passed", edgename)
