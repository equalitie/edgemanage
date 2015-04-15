import sys
import time
import json
import argparse

# Period in minutes
ROTATION_PERIOD=10

OUTPUT_LABEL = "EDGE_ROTATE"
STATUS_MAP = {0: "OK",
              1: "WARN",
              2: "CRIT",
              3: "UKNOWN"}

class CheckRotation(object):

    def __init__(self, state_file):
        with open(state_file) as state_f:
            self.state_info = json.loads(state_f.read())

    def check_rotation(self, warn, crit):
        time_now = time.time()
        nagios_status = 0
        perf_data = 0
        if not self.state_info["rotation_list"] or \
           len(self.state_info["rotation_list"]) < ROTATION_PERIOD:
            nagios_status = 3
            nagios_message = "Not enough rotation data"
        else:
            window_start = time_now - (ROTATION_PERIOD * 60)
            rotations = [ i for i in self.state_info["rotation_list"] \
                          if i > window_start and i < time_now ]
            perf_data = len(rotations)
            nagios_message = "%d in %d seconds" % (perf_data, ROTATION_PERIOD * 60)

        if len(rotations) >= crit:
            nagios_status = 2
        elif len(rotations) >= warn:
            nagios_status = 1

        return (nagios_status, "%s %s %s | frequency=%d" % (OUTPUT_LABEL,
                                                            STATUS_MAP[nagios_status],
                                                            nagios_message, perf_data))

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Nagios check for Edgemanage rotation frequency.')
    parser.add_argument("statefile", nargs=1, action="store",
                        help="Path to the edgemanage state file")
    parser.add_argument("--warn", "-w", action="store", dest="warn",
                        help="Path to the edgemanage state file",
                        default=4, type=int)
    parser.add_argument("--critical", "-c", action="store", dest="crit",
                        help="Path to the edgemanage state file",
                        default=8, type=int)
    args = parser.parse_args()

    c = CheckRotation(args.statefile[0])
    status, message = c.check_rotation(args.warn, args.crit)
    print message
    sys.exit(status)
