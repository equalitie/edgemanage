# Default configuration path
CONFIG_PATH="/etc/edgemanage/edgemanage.yaml"
# Timeout to fetch objects over HTTP
FETCH_TIMEOUT=10
# Times to retry fetching an object if failed
FETCH_RETRY=3

# Number of objects to store in fetch histories
FETCH_HISTORY=2000

# Number of seconds that define a window within which to search for
# fetch entries. Used in a case where we want to check the last $N
# seconds worth of values fetched for a paritcular edge to give us a
# more accurate average than simply averaging the last FETCH_HISTORY
# entries.
DECISION_SLICE_WINDOW=300

# Amount of time within which to check for a rotation in order to
# change Nagios state to WARNING.
NAGIOS_WARNING_TIME = 300

# Number of historical rotations to keep in the state file.
STATE_HISTORICAL_ROTATIONS = 10

# Upper domain to use for looking up IP addresses of edges while
# populating zone files
UPPER_DOMAIN="deflect.ca"
