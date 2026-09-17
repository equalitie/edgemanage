FROM debian:bookworm-slim

RUN set -x \
  && DEBIAN_FRONTEND=noninteractive apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    bind9 \
    bind9-utils \
    bind9-dnsutils \
  && rm -rf /var/lib/apt/lists/*

COPY docker/bind/named.conf /etc/bind/named.conf
COPY docker/conf/rndc.key /etc/bind/rndc.key
COPY docker/bind/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

EXPOSE 53/udp 53/tcp 953/tcp

CMD ["/usr/local/bin/entrypoint.sh"]
