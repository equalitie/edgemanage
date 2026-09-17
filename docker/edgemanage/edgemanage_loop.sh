#!/bin/sh
#
# Run edge_manage on a loop, logging to stdout. The production image uses cron
# and tails a logfile; for local testing we want the output in
# `docker compose logs -f edgemanage` instead.

set -u

: "${DNET:=dnet1}"
: "${RUN_INTERVAL:=60}"
: "${EXTRA_ARGS:=}"

echo "edgemanage_loop: dnet=${DNET} interval=${RUN_INTERVAL}s extra_args='${EXTRA_ARGS}'"

# edge_manage refuses to run within 30s of the last run unless --force, so an
# interval below that needs EXTRA_ARGS=--force in the compose file.
while true; do
    # -v logs to stderr rather than to `logpath`.
    edge_manage -A "$DNET" -v $EXTRA_ARGS || echo "edgemanage_loop: edge_manage exited $?"
    sleep "$RUN_INTERVAL"
done
