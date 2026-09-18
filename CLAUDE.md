# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Edgemanage picks the healthiest hosts ("edges") out of a pool by timing an HTTP fetch of a known
test object from each one, then writes bind-compatible zone files whose apex A records point at the
winners. It is a cron-driven batch job (default every 60s), not a service. Python 3, packaged with
setuptools; three console scripts live in [edgemanage/](edgemanage/) with no `.py` extension:
`edge_manage` (the rotation run), `edge_query` (read edge state), `edge_conf` (set edge mode).

## Commands

```bash
tox                              # full gate: pylint -E + flake8 (max-line-length 100) + pytest
tox -e style                     # lint only
pytest                           # unit tests
pytest tests/test_decisionmaker.py::TestDecisionMaker::test_name   # single test
pip install -r requirements.txt -r test-requirements.txt
python setup.py install          # required before integration tests (see below)
```

Dependencies are locked with [uv](https://github.com/astral-sh/uv). The `.in` files are the
hand-edited sources and the `.txt` files are generated, pinned and hash-checked; never edit a
`.txt` by hand. Regenerate after editing an `.in` (runtime lock first, the test lock constrains
against it):

```bash
uv pip compile requirements.in -o requirements.txt \
    --python-version 3.9 --generate-hashes
uv pip compile test-requirements.in -o test-requirements.txt \
    --python-version 3.9 --generate-hashes -c requirements.txt
```

Runtime versions are pinned to the production server's `pip freeze`, with transitive pins held in
`constraints.txt`. `setuptools<81` is pinned deliberately: `edge_manage` imports `pkg_resources`
at startup for `--version`, and setuptools 81 drops it. See INSTALL.md for the full workflow.

Integration tests ([tests/test_edge_manage_integration.py](tests/test_edge_manage_integration.py))
spawn a Flask server via pexpect and shell out to `edge_manage`, so they need the package
**installed on PATH** and must run **from the repo root**: they read `conf/edgemanage.yaml` and
`tests/test_data/` by relative path. They also assert on wall-clock runtime (e.g. under 1.5s for 20
edges), so they are flaky on loaded machines; that is expected, not a regression to "fix" by
loosening unrelated code.

They only override *some* of the paths in `conf/edgemanage.yaml`, so they inherit the real
`prometheus_logs` (`/var/log/prom/`) and `named_dir` (`/var/cache/bind/`). Those do not exist on a
developer laptop, so **run the suite in Docker**, which creates them
([docker/test/Dockerfile](docker/test/Dockerfile)); all 20 tests pass there:

```bash
docker compose run --rm test                  # whole suite, ~25s
docker compose build test                     # after editing source
```

The service is behind a `test` profile, so `docker compose up` ignores it. Do not "fix" a local
`/var/log/prom/` failure by editing the config or the test.

CI is GitHub Actions ([.github/workflows/python-app.yml](.github/workflows/python-app.yml)) on
Python 3.9.25 running `tox`. A legacy CircleCI config is still present but the Actions workflow is
the live one.

## Architecture

One run of `edge_manage -A <dnet>` is a pipeline. `dnet` ("Deflect network") is the unit of
everything: edge list file, state file, zone template dir, canary file, and live list are all keyed
or `{dnet}`-templated by it.

1. **[edge_manage](edgemanage/edge_manage)**: loads YAML config, acquires an fcntl lock
   (`util.acquire_lock`), refuses to run within 30s of the last run unless `--force`, loads the
   `StateFile` JSON, loads the flat edge list, then calls into `EdgeManage`. Also runs the
   `commands.run_before` / `run_after` / `run_after_changes` hooks and writes Prometheus metrics.
2. **[EdgeManage](edgemanage/edgemanage.py)**: the orchestrator and the file you will spend most
   time in. `do_edge_tests()` fans out fetches over a `ThreadPoolExecutor`; `make_edges_live()`
   selects the live set and renders zone files.
3. **[EdgeTest](edgemanage/edgetest.py)**: one fetch. Resolves the edge hostname itself, then uses
   the `OverrideDNS` context manager to monkeypatch `socket.getaddrinfo` so `requests` hits that
   specific IP while sending the configured `Host` header. Compares the md5 of the response against
   the local copy of the test object. Raises `VerifyFailed` / `FetchFailed`.
4. **[DecisionMaker](edgemanage/decisionmaker.py)**: turns fetch times into a judgement per edge,
   one of `const.VALID_HEALTHS`. Order matters and is load-bearing: last value under `goodenough`
   → `pass_threshold`; last value == `FETCH_TIMEOUT` → `fail` (checked *before* averages, so a
   fresh failure can't be masked by a good history); `DECISION_SLICE_WINDOW`-second average under
   `goodenough` → `pass_window`; lifetime average under it → `pass_average`; else `pass`.
5. **[EdgeList](edgemanage/edgelist.py)**: the chosen set, plus `generate_zone()`, which resolves
   each live edge to an IP and renders
   [templates/zonetemplate.j2](edgemanage/templates/zonetemplate.j2) around the operator-supplied
   per-domain include file. Serial number is `int(time.time())`.

### Selection logic in `make_edges_live()`

Stability is the point: DNS is only changed when it has to be. Edges previously live and still
`pass_threshold` are kept (`check_last_live()`); if that fills `edge_count` (or the per-dnet
`dnet_edge_count` override), nothing is rewritten. Otherwise the shortfall is filled by walking
health tiers best-first (`pass_threshold`, `pass_window`, `pass_average`, `pass`), taking the
fastest in each. If all tiers are exhausted, the last live set is re-added even though it is
failing, on the grounds that stale edges beat an empty A record set. Edge `mode` (`available`,
`force`, `blindforce`, `unavailable`; see [const.py](edgemanage/const.py)) is applied on top and
is set out-of-band by `edge_conf`.

Zone files are rewritten only when the edge list changed, a canary changed, the template's mtime
changed, or `--force-update` was passed. Both the `for/else` constructs and the mtime bookkeeping
in `state_obj.zone_mtimes` exist for this; be careful editing them.

### Canaries

Per-zone extra IPs from `canary_files`, tracked by a **separate** `DecisionMaker` and never counted
toward `edge_count`. A healthy canary displaces one random live edge in that zone's file only. If
`canary_killer` canaries fail, all remaining canary futures are cancelled and every canary is
force-failed, because they usually share a host, so a few failures imply the whole box is gone. Canaries
are always stored with state `out`.

### Persistence

Two flat-file stores, both hand-rolled and both with back-compat quirks:

- **[EdgeState](edgemanage/edgestate.py)**: one JSON `<edge>.edgestore` per edge under
  `healthdata_store`, holding `fetch_times` (capped at `FETCH_HISTORY`), hourly
  `historical_average`, rotation history, mode, state, health, comment. Missing keys are backfilled
  from `ASSUMED_VALS`, which is the migration mechanism for adding a field. Writes go through
  `util.open_atomic` because a truncated statefile blocks future runs. Note `fetch_times` keys are
  timestamps cast to **strings**, a documented legacy hack; code reading them does `float(ts)`.
- **[StateFile](edgemanage/statefile.py)**: one JSON blob per dnet: `last_live`, `last_run`,
  `rotation_list`, `zone_mtimes`, `active_canaries`. Same pattern: defaults set in `__init__`, then
  overwritten from the loaded dict, so new fields are additive.

Corrupt or unparsable edge state is logged and skipped rather than fatal; several call sites depend
on an edge being absent from `edge_states` mid-run.

### Other pieces

[monitor.py](edgemanage/monitor.py) is a singleton Prometheus registry written to a textfile at the
end of a run; gauges must be created up front from the edge list, and `Monitor().set()` silently
drops unknown keys. [adapter.py](edgemanage/adapter.py) (`EdgemanageAdapter`) is a non-CLI entry
point used by Django callers to read config and reconcile dnet edge-list files.
[nagios/](nagios/) checks are deliberately stdlib-only and read the state and health files directly.

## Conventions

- Python 3, but `six`, `from __future__ import absolute_import` and `six.iteritems` are still
  everywhere; match the surrounding file rather than modernizing in passing.
- flake8 at 100 columns; pylint runs errors-only (`-E`). Several `# pylint: disable=no-member` are
  load-bearing where attributes are set dynamically from `ASSUMED_VALS`.
- `const.FETCH_TIMEOUT` doubles as the sentinel "this edge failed" fetch time; don't introduce a
  separate failure value without updating `DecisionMaker`.
- The config key `testing: true` changes behavior (raw IP sent as the `Host` header, `timeout`
  overrides `FETCH_TIMEOUT`) and exists for the integration suite.
- Branches: `develop` is the main branch; releases and hotfixes merge via PR.
