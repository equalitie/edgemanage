# Test runner image for edgemanage. Build context is the repo root.
#
# The integration suite reads conf/edgemanage.yaml but only overrides some of
# its paths, so it inherits the real `prometheus_logs` (/var/log/prom/) and
# `named_dir` (/var/cache/bind/) from that file. Neither exists on a developer
# laptop, which is why those tests fail there and pass in here: this image
# creates them. Same 3.9 base as docker/edgemanage/Dockerfile.
FROM python:3.9-slim-bookworm

# The paths conf/edgemanage.yaml refers to and the integration suite does not
# override. /var/log/prom is the one the prometheus textfile writer needs.
RUN mkdir -p /etc/edgemanage/edges \
             /etc/edgemanage/zones \
             /etc/edgemanage/canaries \
             /var/lib/edgemanage/health \
             /var/lock/edgemanage \
             /var/tmp/edgemanage \
             /var/log/edgemanage \
             /var/log/prom \
             /var/cache/bind

# Dependencies first, so editing source does not invalidate the install layer.
# --require-hashes makes the locks authoritative: the build fails rather than
# silently drifting if a lock and its hashes disagree.
COPY requirements.txt test-requirements.txt /src/
RUN pip install --no-cache-dir --require-hashes \
      -r /src/requirements.txt \
      -r /src/test-requirements.txt

# Editable, matching the dev image: a bind-mounted working tree wins over what
# was baked in, so tests can be re-run without a rebuild.
COPY . /src
RUN pip install --no-cache-dir --no-deps -e /src

# The suite shells out to `edge_manage` and reads conf/ and tests/test_data/ by
# relative path, so it has to run from the repo root.
WORKDIR /src

CMD ["pytest", "-v"]
