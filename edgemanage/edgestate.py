import os
import json
import time
import logging
import datetime
import copy

from const import FETCH_HISTORY, VALID_MODES, VALID_HEALTHS

ASSUMED_VALS={
    # A list of timestamps of when this edge has been in rotation
    "rotation_history": [],
    # A dict keyed by timestamps with values of floats containing
    # fetch times - limited to FETCH_HISTORY items
    "fetch_times": {},
    # A dict keyed by timestamps which keeps an average of fetch times
    # for FETCH_HISTORY days
    "historical_average": {},
    "state": "out",
    "mode": "available",
    "health": "pass",
    "state_entry_time": None,
    # A comment created by edge_conf when changing state
    "comment": "",
}

class EdgeState(object):

    def __init__(self, edgename, store_dir, nowrite=False):
        '''An object representing a simple set of time series data,
        backed by a local JSON file store. Also some state variables.

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
                except KeyError as e:
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
            return

        for val_key, val_type in ASSUMED_VALS.iteritems():
            output[val_key] = getattr(self, val_key)
        with open(self.statfile, "w") as statfile_f:
            json.dump(output, statfile_f, sort_keys=True, indent=4)

    def set_comment(self, comment):
        self.comment = comment
        self._dump()

    def unset_comment(self):
        self.comment = ""
        self._dump()

    def set_health(self, health):
        if health not in VALID_HEALTHS:
            raise ValueError("Health must be one f %s, not %s",
                             str(VALID_HEALTHS), health)
        else:
            if self.health != health:
                logging.debug("Setting health for edge %s to %s", self.edgename, health)
                self.health = health
                self._dump()

    def set_state(self, state):
        ''' Set the state of the edge - in or out '''
        if state not in ["in", "out"]:
            raise ValueError("State must be either in or out, not %s", state)
        else:
            if self.state != state:
                self.state = state
                self._dump()

    def set_mode(self, mode):
        ''' Set the mode of the edge '''
        if mode not in VALID_MODES:
            raise ValueError("Mode %s isn't in the set of valid modes (%s)",
                             mode, str(VALID_MODES))
        else:
            if self.mode != mode:
                self.state_entry_time = time.time()
                self.mode = mode
                self._dump()

    def current_average(self):
        ''' Return an average of the current live set of values '''
        return sum(self.fetch_times.values())/len(self.fetch_times)

    def __len__(self):
        ''' Return the number of values for fetch times we have '''
        return len(self.fetch_times)

    def __getitem__(self, index):
        '''Return the datetime at a given timestamp - or return a slice of
        dates between two timestamps
        '''
        if isinstance(index, slice):
            return_dict = {}
            for key, val in self.fetch_times.iteritems():
                if key >= index.start and key <= index.stop:
                    return_dict[key] = val

            return return_dict
        else:
            return self.fetch_times[index]

    def last_value(self):
        ''' Get the most recent value stored '''
        return self.fetch_times[max(self.fetch_times.keys())]

    def add_rotation(self):
        self.rotation_history.append(time.time())
        self._dump()

    def add_value(self, new_value, timestamp=None):
        '''Add a new value to the fetch times store and check if we
        need to make a historical average

        '''

        if timestamp:
            the_time = timestamp
        else:
            the_time = time.time()

        # HACK: for legacy reasons, we need to cast to string
        # here. It's stupid. Need to fix this in future versions with
        # migration path for old state files.
        self.fetch_times[str(the_time)] = new_value

        # prune our values if there's too many of them
        if len(self.fetch_times) > FETCH_HISTORY:
            min_value = sorted(self.fetch_times.keys())[0]
            logging.debug("Rotating out item with timestamp %s and value %f due to fetch cache being over %d items",
                          min_value, self.fetch_times[min_value], FETCH_HISTORY)
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
