# Local Docker test harness

A self-contained `docker compose` stack for exercising edgemanage end to end on a laptop: eight
fake origins standing in for edges and canaries, a bind9 instance serving the zones edgemanage
generates, and an edgemanage container built from **your working tree**.

This is a development harness, not a deployment artifact. The production image lives elsewhere.

## Quickstart

```bash
docker compose build
docker compose up -d
docker compose logs -f edgemanage
```

Then watch the result in DNS:

```bash
dig @127.0.0.1 -p 5354 test.local +short +tcp
dig @127.0.0.1 -p 5354 www.test.local +short +tcp
```

`+tcp` is there for Docker Desktop on macOS, whose published-UDP path does not return DNS replies
to the host (the query reaches named, the answer never comes back). UDP works from inside the
compose network and on Linux, so drop the flag if you are not on a Mac:

```bash
docker compose exec edgemanage dig @bind test.local +short
```

Tear down with `docker compose down`, or `docker compose down -v` to also wipe health data, state
and generated zones.

## What is in the stack

Network `em-edgenet`, subnet `172.28.0.0/24`. Addresses are static because canaries must be
literal IPs — `edge_manage` validates them with `ipaddr.IPAddress` and silently drops anything
that isn't one.

| Service | IP | Behaviour | Expected health |
|---|---|---|---|
| `edgemanage` | .5 | runs `edge_manage -A dnet1 -v` every 60s | — |
| `bind` | .6 | serves `named_dir`, published on host port 5354 | — |
| `edge1` | .11 | responds in 0.02s | `pass_threshold` |
| `edge2` | .12 | responds in 0.05s | `pass_threshold` |
| `edge3` | .13 | responds in 0.1s | `pass_threshold` |
| `edge4` | .14 | responds in 0.4s | `pass_threshold` |
| `edge5` | .15 | responds in 3s | `pass` — over `goodenough`, so held in reserve |
| `edge6` | .16 | returns HTTP 500 | `fail` (`FetchFailed`) |
| `canary1` | .101 | responds in 1.5s | `pass` — displaces one edge in `test.local` |
| `canary2` | .102 | serves the wrong bytes | `fail` (`VerifyFailed`), never used |

`edge_count` is 4, so four of the six edges go live and the selection tiers in `make_edges_live()`
actually have work to do.

### Why the working canary is the slow one

`canary1` responds in 1.5s rather than something quick, which looks backwards until you read the
substitution check in `make_edges_live()`: a canary is only used when its health is exactly `pass`
or `pass_window`. `pass_threshold` — the *best* tier, and what a fast canary earns — is not in that
list, so a canary quicker than `goodenough` is logged as "configured as a canary but it is in state
pass_threshold so it will not be used" and silently skipped.

A steady delay above `goodenough` (0.700) and below `const.FETCH_TIMEOUT` (10) is therefore what
puts a canary into a tier that actually gets substituted. Worth knowing before you conclude your
canaries are broken.

## Changing how an edge behaves

Each origin reads its behaviour from environment variables on every request. Edit the service in
[docker-compose.yml](../docker-compose.yml) and `docker compose up -d <service>`:

| `MODE` | Effect on edgemanage |
|---|---|
| `ok` (default) | serves the test object after `DELAY` seconds |
| `500` | `FetchFailed`, fetch time recorded as `const.FETCH_TIMEOUT` |
| `corrupt` | `VerifyFailed` — md5 mismatch against the local test object |
| `hang` | sleeps 30s, past `const.FETCH_TIMEOUT`, so the fetch times out |
| `close` | drops the connection, exercising the `FETCH_RETRY` retry loop |

`DELAY` is a float in seconds and is what drives the health tiers, against `goodenough: 0.700` in
[docker/conf/edgemanage.yaml](conf/edgemanage.yaml).

To force a rotation, break one of the live edges and wait a loop. Either edit `MODE` for that
service in the compose file and `docker compose up -d edge1`, or keep the compose file clean and
use a throwaway override:

```bash
cat > /tmp/break-edge1.yml <<'EOF'
services:
  edge1:
    environment:
      EDGE_NAME: edge1
      MODE: "500"
EOF
docker compose -f docker-compose.yml -f /tmp/break-edge1.yml up -d edge1
docker compose logs -f edgemanage
docker compose up -d edge1          # put it back
```

Expect `edge1` to be discarded, `edge5` promoted out of the `pass` tier to fill the gap, a fresh
zone file with a new serial, and `server reload successful` from the rndc hook.

The zone file is only rewritten when the edge list changed, a canary changed, a template's mtime
changed, or `--force-update` was passed — so on a steady-state run you should see
`Not writing zonefile for test.local because there are no changes pending`.

## Poking at a running stack

```bash
# Current view of every edge
docker compose exec edgemanage edge_query -A dnet1 -f json

# One-off dry run, nothing written
docker compose run --rm edgemanage edge_manage -A dnet1 -v -n

# The generated zone, include file and all
docker compose exec edgemanage cat /var/cache/bind/test.local.zone

# Prometheus textfile output
docker compose exec edgemanage cat /var/log/prom/edgemanage.prom

# Take an edge out of rotation by hand
docker compose exec edgemanage edge_conf -A dnet1 -m unavailable -C "testing" edge2
```

## Live-editing edgemanage

The image does `pip install -e /src`, and compose bind-mounts `./edgemanage` over
`/src/edgemanage`, so changes to the Python package — including
[templates/zonetemplate.j2](../edgemanage/templates/zonetemplate.j2) — take effect on the next loop
iteration with no rebuild.

The three console scripts (`edge_manage`, `edge_query`, `edge_conf`) are an exception: setuptools
*copies* them into `/usr/local/bin` at install time. To test an edit to one of those without
rebuilding, run it out of the mount:

```bash
docker compose exec edgemanage python3 /src/edgemanage/edge_manage -A dnet1 -v -n
```

## Running the test suite

The integration tests read `conf/edgemanage.yaml` but only override some of its paths, so they
inherit the real `prometheus_logs` (`/var/log/prom/`) and `named_dir` (`/var/cache/bind/`). Neither
exists on a developer laptop, so those tests fail there for reasons that have nothing to do with
the code. [docker/test/Dockerfile](test/Dockerfile) creates them, which is the point of running the
suite in a container:

```bash
docker compose run --rm test                            # whole suite
docker compose run --rm test pytest tests/test_edgelist.py   # one file
docker compose run --rm test pytest -k canary -v         # one pattern
docker compose run --rm test flake8 edgemanage tests     # lint instead
```

The service sits behind a `test` profile, so `docker compose up` ignores it, and it needs none of
the other services: the suite spawns its own Flask server and reaches it over loopback.

The image COPYs the working tree rather than bind-mounting it, so a run tests what is committed
rather than whatever is on disk. Rebuild to pick up local edits:

```bash
docker compose build test && docker compose run --rm test
```

Dependencies come from the hash-checked locks with `--require-hashes`, so the versions under test
are the ones in `requirements.txt`, not whatever is newest on PyPI. That is the other reason to
prefer this over a laptop virtualenv.

The wall-clock assertions (`assertLess(self.running_time, 6)` and friends) still apply in here.
They pass with room to spare on an idle machine but are the first thing to fail if the host is
loaded; that is a property of the tests, not a regression.

## Why `workers: 1`

The harness config pins `workers: 1`. `OverrideDNS` in
[edgetest.py](../edgemanage/edgetest.py) swaps the module-global `socket.getaddrinfo` with no
locking, while `do_edge_tests()` fans fetches out over a `ThreadPoolExecutor`. With more than one
worker *and* edges on distinct IPs — which is the case here, unlike the integration suite where
every edge is `127.0.0.x` on one server — one thread's override can be in force while another
thread is resolving, so a fetch can end up timed against the wrong edge.

Raising `workers` is the quickest way to observe that; leave it at 1 for results you can trust.

## Differences from the production image

- Base is `python:3.9-slim-bookworm`, not `debian:buster-slim`. Buster is EOL and its apt repos are
  archived, and `requirements.txt` pins `ipaddr==2.2.0`, which has no wheel for modern
  interpreters. The image installs via `setup.py`'s unpinned `install_requires` instead, unlike the
  test image, which installs the hash-checked locks. `edge_manage` imports `pkg_resources` at
  startup, so it needs the `setuptools<81` pin the locks now carry.
- edgemanage is installed from the local checkout, not `pip install git+https://...`.
- A shell loop replaces cron, so logs go to stdout.
- `testing: true` is **not** set. Every edge is its own container, so the real `Host: test.local`
  header works and the run exercises the same request shape as production — something the
  integration suite cannot do.

## Security note

[docker/conf/rndc.key](conf/rndc.key) is a fixed key committed so that `docker compose up` works
with no setup step, and the bind `controls` stanza allows any source on the compose network. That
is fine for a throwaway local network and nowhere else.
