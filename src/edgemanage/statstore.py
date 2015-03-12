import os
import json
import time
import logging
import datetime
import copy

from const import FETCH_HISTORY

ASSUMED_VALS={
    # A list of timestamps of when this edge has been in rotation
    "rotation_history": [],
    # A dict keyed by timestamps with values of floats containing
    # fetch times - limited to FETCH_HISTORY items
    "fetch_times": {},
    # A dict keyed by timestamps which keeps an average of fetch times
    # for FETCH_HISTORY days
    "historical_average": {}
}

class StatStore(object):

    def __init__(self, edgename, store_dir, nowrite=False):
        '''An object representing a simple set of time series data,
        backed by a local JSON file store

         Aka: Anything but RRD.
        '''

        self.edgename = edgename
        self.nowrite = nowrite
        self.statfile = os.path.join(store_dir, "%s.edgestore" % edgename)
        if os.path.isfile(self.statfile) and os.path.getsize(self.statfile) != 0:
            with open(self.statfile) as statfile_f:
                stat_info = json.load(statfile_f)
            for val_key, val_type in ASSUMED_VALS.iteritems():
                # Set self attributes for all dict vals in the stat
                # store.
                try:
                    setattr(self, val_key, stat_info[val_key])
                except AttributeError as e:
                    # If the stat store lacks one of the keys in the
                    # dict, then initialise it with the default value
                    # from ASSUMED_VALS (usually just a type) - this
                    # lets us add new fields as we go along. Like a
                    # database migration for flat files :)
                    logging.error("Edgefile %s lacks %s, assuming %s", self.statfile,
                                  val_key, str(val_type))
                    setattr(self, val_key, copy.copy(val_type))
        else:
            # There is no stat file, just load empty assumed vals
            logging.warning("Initialising previously untracked edge %s", self.edgename)
            for val_key, val_type in ASSUMED_VALS.iteritems():
                setattr(self, val_key, copy.copy(val_type))

    def _dump(self):
        ''' Write out stat data to file '''
        output = {}

        if self.nowrite:
            logging.debug("Not writing %s because nowrite=True", self.statfile)

        for val_key, val_type in ASSUMED_VALS.iteritems():
            output[val_key] = getattr(self, val_key)
        with open(self.statfile, "w") as statfile_f:
            json.dump(output, statfile_f)

    def current_average(self):
        ''' Return an average of the current live set of values '''
        return sum(self.fetch_times.values())/len(self.fetch_times)

    def __len__(self):
        ''' Return the number of values for fetch times we have '''
        return len(self.fetch_times)

    def last_value(self):
        ''' Get the most recent value stored '''
        return self.fetch_times[max(self.fetch_times)]

    def add_value(self, new_value):
        '''Add a new value to the fetch times store and check if we
        need to make a historical average

        '''

        the_time = time.time()
        self.fetch_times[the_time] = new_value

        # prune our values if there's too many of them
        if len(self.fetch_times) > FETCH_HISTORY:
            min_value = sorted(self.fetch_times.keys())[0]
            logging.debug("Rotating out item with timestamp %f due to fetch cache being over %d items",
                          min_value, FETCH_HISTORY)
            del(self.fetch_times[min_value])

        the_time_datetime = datetime.datetime.utcfromtimestamp(the_time)
        if the_time_datetime.minute == 0:
            # prune our values if there's too many of them
            if len(self.historical_average) > FETCH_HISTORY:
                min_value = sorted(self.historical_average.keys())[0]
                del(self.historical_average[min_value])
            self.historical_average[the_time] = self.current_average()

        self._dump()
        return the_time
