import sys
import time
import json

# This needs to be made an argument but for now it's here. If not
# fixed this script isn't much use.

WARNING_THRESHOLD=300

class CheckRotation(object):

    def __init__(self, state_file):
        with open(state_file) as state_f:
            self.state_info = json.loads(state_f.read())

    def check_rotation(self):
        time_now = time.time()
        nagios_status = 0
        perf_data = 0
        if not self.state_info["rotation_list"]:
            nagios_status = 3
            nagios_message = "No last rotation time"
        else:
            perf_data = time_now - self.state_info["rotation_list"][-1]
            nagios_message = "Last rotation was %d seconds ago" % (time_now - self.state_info["rotation_list"][-1])
        if (time_now - self.state_info["rotation_list"][-1]) < WARNING_THRESHOLD:
            nagios_status = 1

        return (nagios_status, "%s | %d" % (nagios_message, perf_data))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stderr.write("Need one argument - a path to the Edgemanage state file")

    c = CheckRotation(sys.argv[1])
    status, message = c.check_rotation()
    print message
    sys.exit(status)
