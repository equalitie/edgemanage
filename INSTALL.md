Installing Edgemanage
========

Requirements
--------

If installing on a Debian-based system, you'll probably need to do
`apt-get install python-yaml python-requests python-jinja2 python-concurrent.futures python-setuptools python-setproctitle build-essential`.

Alternatively, if using `pip`, simply run `pip install -r
requirements.txt`.

`requirements.txt` is a fully pinned, hash-checked lock file, so that
command installs exactly the versions edgemanage is tested against. It
needs no extra tooling -- plain `pip` is enough.

Dependency locking
--------

The lock files are generated with [uv](https://github.com/astral-sh/uv)
and committed. The hand-edited sources are the `.in` files; the `.txt`
files are generated output and should not be edited directly.

| File | Role |
|---|---|
| `requirements.in` | direct runtime dependencies |
| `constraints.txt` | transitive pins, snapshotted from production |
| `requirements.txt` | generated runtime lock (pinned + hashes) |
| `test-requirements.in` | direct test/lint dependencies |
| `test-requirements.txt` | generated test lock (pinned + hashes) |

To change a dependency, edit the relevant `.in` file and recompile.
The target is Python 3.9, matching CI and the docker image:

```bash
uv pip compile requirements.in -o requirements.txt \
    --python-version 3.9 --generate-hashes

uv pip compile test-requirements.in -o test-requirements.txt \
    --python-version 3.9 --generate-hashes -c requirements.txt
```

Recompile the runtime lock first: the test lock constrains itself
against it so that shared packages (Jinja2, MarkupSafe) do not diverge
between the two.

To pick up new upstream releases rather than just re-resolving, add
`--upgrade`, or `--upgrade-package <name>` for a single one.

Installation
--------

Run `python setup.py install`. Unless you have a bindir and libdir that is
owned by your user, you'll need to do this as root.

Configuration
--------

These instructions assume that your edgemanage config lives at
`/etc/edgemanage/`, and that the network is named "mynet". These are
arbitrary suggestions, put stuff where you like!

* Create the directories we'll need:
    * `/etc/edgemanage/{zones,edges}`
    * `/var/lib/edgemanage/health`
    * Wherever your zone files get written to (`/var/cache/bind` by default)
* Copy `conf/edgemanage.yaml` to `/etc/edgemanage/`
* Set up your edge list in `/etc/edgemanage/edges/mynet`. Edge lists
  are just flat files with a newline-separated list of hosts to be
  queried.
* Set up your edgemanage object - This could be anything from a tiny
  text file to a large image, whatever is most reprensentative of your
  caching setup (if you serve lots of HTML/images/whatever). Store it
  at /etc/edgemanage/myobject.edgemanage and configure the
  `testobject` section of `edgemanage.yaml` accordingly. Also deploy
  this object to the edges that you will be querying.
* Set up your zone include files - there needs to be a file for each
  domain you want to use edgemanage for in
  `/etc/edgemanage/zones/mynet`, named like `example.com.zone`. These
  files need to be standard Bind-style files and the main limitation
  is that they cannot contain an SOA record.  If you don't have any
  records other than your rotating @ A records, simply create an empty
  file.
* Do a dry run to make sure everything's okay without writing any
  files out: `edge_manage -A mynet -n`
