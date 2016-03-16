import json
import time

class StateFile(object):

    ''' A simple stat storage object, a glorified dict '''

    def __init__(self, existing_dict={}):

        # The list of time.times()s indicating when we last rotated
        self.rotation_list = []
        # the time.time() we last ran
        self.last_run = None
        # a list of the last live edges
        self.last_live = []
        # A list of failures last run
        self.verification_failues = []
        # A list of mtimes for zonefiles
        self.zone_mtimes = {}

        # Restore any existing saved values - setting values above
        # this means that we can add new values to the state file
        # without any worries of them saving.
        for key, val in existing_dict.iteritems():
            setattr(self, key, val)

    def set_last_run(self):
        ''' update when we last ran. '''
        self.last_run = time.time()

    def to_json(self):
        ''' dump a representation of keys/vals for storage. '''
        return json.dumps(self.__dict__)

    def last_rotation(self):
        if self.rotation_list:
            return self.rotation_list[-1]
        else:
            return None

    def add_rotation(self, max_rotations, newtime=None):
        ''' Add a rotation, rotate out oldest value.

         newtime: optional epoch time to manually append instead of
        the current tiem.

        '''

        if len(self.rotation_list) == max_rotations:
            # We have too many historical rotations, remove one
            self.rotation_list = self.rotation_list[1:]

        if newtime:
            self.rotation_list.append(newtime)
        else:
            self.rotation_list.append(time.time())
