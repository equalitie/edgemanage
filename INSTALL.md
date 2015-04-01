Installing Edgemanage
========

Requirements
--------

If installing on a Debian-based system, you'll probably need to do
`apt-get install python-requests python-jinja2`. Odds are you will
also need to `apt-get install python-concurrent.futures`, this depends
on the version of Python you're running and also how your maintainer
has built it - Debian wheezy requires this package.

If using `pip`, simply run `pip install -r requirements.txt`.

Installation
--------

`python setup.py install`. Unless you have a bindir and libdir that
isn't owned by your user, you'll need to do this as root.

Configuration
--------

These instructions assume that your edgemanage config lives at
`/etc/edgemanage/`, and that the network is named "mynet". These are
arbitrary suggestions, put stuff where you like!

* Create the directories we'll need:
    * `/etc/edgemanage/{zones,edges}`
    * `/var/lib/edgemanage/health`
    * Wherever your zone files get written to (`/var/cache/named` by default)
* Copy `conf/edgemanage.yaml` to `/etc/edgemanage/`
* Set up your edge list in `/etc/edgemanage/edges/mynet`. Edge lists
  are just flat files with a newline-separated list of hosts to be
  queried.
* Set up your edgemanage object - This could be anything from a tiny
  text file to a large image, whatever is most reprensentative of your
  caching setup (if you serve lots of HTML/images/whatever). Store it
  at /etc/edgemanage/myobject.edgemanage and configure the
  `testobject` section of `edgemanage.yaml` accordingly.
* Set up your zone files - there needs to be a file for each domain
  you want to use edgemanage for in `/etc/edgemanage/zones/mynet`,
  named like `example.com.zone`. If you don't have any records other
  than your rotating @ A records, simply create an empty file.
* Do a dry run to make sure everything's okay without writing any
  files out: `edge_manage -A mynet -n`