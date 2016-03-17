Installing Edgemanage
========

Requirements
--------

If installing on a Debian-based system, you'll probably need to do
`apt-get install python-yaml python-requests python-jinja2 python-concurrent.futures python-setuptools python-setproctitle build-essential`.

Alternatively, if using `pip`, simply run `pip install -r
requirements.txt`.

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
