# Local development image for edgemanage. Build context is the repo root.
#
# This is deliberately not the production deflect image: it installs the local
# working tree in editable mode so that uncommitted changes are picked up on the
# next run without a rebuild.
#
# Base is python:3.9 rather than debian:buster-slim because buster is EOL (its
# apt repos are archived) and because requirements.txt pins setproctitle==1.1.10
# and ipaddr==2.2.0, which have no wheels for modern interpreters. 3.9 also still
# ships pkg_resources (setuptools < 81), which edge_manage imports at startup for
# --version. Bookworm rather than bullseye: the bullseye index on deb.debian.org
# currently 404s on superseded package versions.
FROM python:3.9-slim-bookworm

# bind9-utils provides rndc, bind9-dnsutils provides dig for poking at the bind
# container from here.
RUN set -x \
  && DEBIAN_FRONTEND=noninteractive apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    bind9-utils \
    bind9-dnsutils \
    procps \
  && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /etc/edgemanage/edges \
             /etc/edgemanage/zones \
             /etc/edgemanage/canaries \
             /var/lib/edgemanage/health \
             /var/lock/edgemanage \
             /var/tmp/edgemanage \
             /var/log/edgemanage \
             /var/log/prom \
             /var/cache/bind

COPY . /src
RUN pip install --no-cache-dir -e /src

COPY docker/edgemanage/edgemanage_loop.sh /usr/local/bin/edgemanage_loop.sh
COPY docker/edgemanage/healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod 0755 /usr/local/bin/edgemanage_loop.sh /usr/local/bin/healthcheck.sh

WORKDIR /src

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s \
  CMD /usr/local/bin/healthcheck.sh

CMD ["/usr/local/bin/edgemanage_loop.sh"]
