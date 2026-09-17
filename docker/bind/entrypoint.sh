#!/bin/sh
#
# Seed placeholder zone files so named loads cleanly on a fresh volume, then run
# named in the foreground. edgemanage overwrites these on its first run and
# calls `rndc reload`.

set -eu

ZONE_DIR=/var/cache/bind

for zone in test.local example.local; do
    zonefile="${ZONE_DIR}/${zone}.zone"
    if [ ! -s "$zonefile" ]; then
        echo "entrypoint: seeding placeholder zone for ${zone}"
        cat > "$zonefile" <<EOF
; Placeholder written by docker/bind/entrypoint.sh. edgemanage replaces this
; with a generated zone on its first run.
@    300    IN    SOA   ns1.test.local. hostmaster.test.local. 1 43200 10800 1209600 300
@               IN      NS      ns1.test.local.
ns1             300     IN      A       172.28.0.6
EOF
    fi
done

mkdir -p /var/run/named

exec named -g -c /etc/bind/named.conf
