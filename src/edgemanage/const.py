# Default configuration path
CONFIG_PATH="/etc/edgemanage.yaml"
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
