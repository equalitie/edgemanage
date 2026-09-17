#!/bin/sh
#
# Unhealthy if the dnet statefile hasn't had a last_run written within two run
# intervals - i.e. edge_manage is wedged or crashing every iteration.

set -u

: "${DNET:=dnet1}"
: "${RUN_INTERVAL:=60}"

STATEFILE="/var/lib/edgemanage/${DNET}.state"

exec python3 - "$STATEFILE" "$RUN_INTERVAL" <<'EOF'
import json
import sys
import time

statefile, interval = sys.argv[1], int(sys.argv[2])

try:
    with open(statefile) as state_f:
        last_run = json.load(state_f).get("last_run")
except (OSError, ValueError) as e:
    sys.exit("no usable statefile at %s: %s" % (statefile, e))

if not last_run:
    sys.exit("statefile %s has no last_run" % statefile)

age = time.time() - float(last_run)
if age > interval * 2:
    sys.exit("last run was %ds ago, more than two intervals" % age)

print("last run was %ds ago" % age)
EOF
