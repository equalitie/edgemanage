#!/usr/bin/env python

import sys
import time
import json
import argparse
import glob
import os.path

# Default to any failure being a critical failure
DEFAULT_CRIT=1.0

OUTPUT_LABEL="EDGE_TESTMATCH"
STATUS_MAP = {0: "OK",
              1: "WARN",
              2: "CRIT",
              3: "UKNOWN"}

class CheckVerification(object):

    def __init__(self, state_file):
        with open(state_file) as state_f:
            self.state_info = json.loads(state_f.read())

    def check_rotation(self, warn, crit):
        nagios_status = 0

        nagios_message = "All edges returning successfully"

        if "verification_failures" not in self.state_info:
            nagios_message = "No verification data logged!"
            nagios_status = 3
        elif self.state_info["verification_failures"]:
            nagios_status = 2
            nagios_message = "Verification failures on %d edges" % (len(self.state_info["verification_failures"]))

        return (nagios_status, "%s %s %s | notok=%d badedges=%s" % (
            OUTPUT_LABEL,
            STATUS_MAP[nagios_status],
            nagios_message,
            len(self.state_info["verification_failures"]),
            ",".join(self.state_info["verification_failures"])
        ))

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Nagios check for Edgemanage verification failures.')
    parser.add_argument("statefile", nargs=1, action="store",
                        help="Path to the edgemanage state file")
    parser.add_argument("--warn", "-w", action="store", dest="warn",
                        help="Ignored. ",
                        default=1, type=int)
    parser.add_argument("--critical", "-c", action="store", dest="crit",
                        help="Number of failed verifications to set CRIT upon",
                        default=1, type=int)
    args = parser.parse_args()

    c = CheckVerification(args.statefile[0])
    status, message = c.check_rotation(args.warn, args.crit)
    print message
    sys.exit(status)
