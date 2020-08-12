edgemanage3
========

Edgemanage is a tool for managing the HTTP availability of a cluster of
web servers via DNS. The machines tested are expected to be at risk of
large volumes of traffic, attack or other potential instability. If a
machine is found to be underperforming, it is replace by a more
performant host to ensure maximum availability.

Branch build statuses
---------------------

Master: [![Circle CI](https://circleci.com/gh/equalitie/edgemanage/tree/master.svg?style=svg&circle-token=b77f796781934f76fbac3446708f49f544cdac71)](https://circleci.com/gh/equalitie/edgemanage/tree/master)

Develop: [![Circle CI](https://circleci.com/gh/equalitie/edgemanage/tree/develop.svg?style=svg&circle-token=b77f796781934f76fbac3446708f49f544cdac71)](https://circleci.com/gh/equalitie/edgemanage/tree/develop)

Overview
--------

Edgemanage is a simple script and Python library designed to be run at
regular intervals, usually via crontab. The designed usecase was every
60 seconds but larger figures can be used[^1].

Edgemanage fetches an object from a lists of hosts over HTTP and uses
the time taken to retrieve the object to make decisions about which
hosts are healthiest. These hosts are then written to a zone file as A
records for the apex of a domain, in addition to inserting files
stored in the zone includes directory. Simple checksumming of the
local and remote objects also happens after fetching.

The zone files that Edgemanage writes are created via Jinja templates,
with SOA and NS data defined in the configuration file and the output
format being bind-compliant. The per-domain records that are included
are plain ol' Bind style rules. Just don't include any SOA records.

Installation
--------
See [INSTALL.md](https://github.com/equalitie/edgemanage/blob/master/INSTALL.md).

Operation
--------

A host is considered to be in a healthy state (internally called
"pass") when the object is returned under the `goodenough` value set
in the configuration file. Hosts that return the fetched object under
the time specified will always be chosen first in case the need to
replace a host that is not in a healthy state.

Care is taken to ensure that DNS changes are not made where they are
not needed - this means that if the last set of known healthy edges
are in a passing state, there will be no change in DNS.

Edgemanage maintains a store of historical fetches per host and can
make decisions based on this data. By default, if there are not enough
passing hosts, Edgemanage will add hosts based on their average over a
time window, and failing that, their overall average.

Edgemanage needs to be run regularly to be of use. I recommend running
it via cron. If you're setting it up for the first time, I recommend
running it in verbose mode (*-v*) and either dry run mode (*-n*) or
writing to a location that doesn't contain production information.

Edgemanage maintains a statefile that is used for historical
information about previous live hosts and last rotation times.

If a connection to a host is refused, the maximum time allowable will
be assigned to a host (thereby ensuring both its removal from the live
pool and also a backoff window via its averages).

Logging/Output
--------

For debugging, the use of the verbose mode is recommended. Using
verbose mode disables logging to syslog.

The dry run mode will only read the statefile and log/print the
decisions that would be made (use of the verbose switch is
recommended).

Configuration
--------

The "object" that edgemanage focuses could be absolutely anything - in
testing the file that was used was a simple text file. The only
concern is that an object that takes a long time runs the risk of
coming close to theoretical fetch times in slow situation, thereby
potentially interrupting sequential runs. It's also worth noting that
Edgemanage currently uses a simple requests
[get](http://docs.python-requests.org/en/latest/api/#requests.get), so
downloading enormous objects will lead to memory issues. So eh, don't
do that.

Edgemanage supports multiple "networks" - different groups of hosts to
be queried and used for writing zone files.

Edgemanage uses the `dnschange_maxfreq` configuration option to limit
the number of rotations that can be undertaken in a certain time
period. This is to limit churn that could lead to constantly empty
caches and so on.

See the `edgemanage.yaml` file for documentation of the configuration
options.

Canaries
-------

So-called "canary" edges are used to assign individual network
resources to a single zone. They are a completely optional part of
Edgemanage configuration, but may be useful for deploying special
configurations, per-domain systems or for detection/analysis
approaches.

An example of a use of this functionality would be if you had a number
of systems that were present in a network environment where incoming
traffic is filtered upstream somehow. If canaries were to be included
for some domains with IP addresses corresponding to a system with
unfiltered access, the canary IPs can be used for traffic capture and
analysis without needing to discard all other hosts. This approach is
also useful for low-cost setups where many sites are hosted and attack
traffic such as UDP is involved. Using a per-zone IP address allows
for a differential diagnosis of attack traffic, isolating which sites
are attracting attacks.

To give a worked example - mydnet1 has a canary file in
```/etc/edgemanage/canaries/mydnet1```. This path is set in
edgemanage.yaml. On run, the file in
```/etc/edgemanage/canaries/mydnet1``` is loaded and the YAML data is
read (it should contain only a list of site: ipaddress pairs). Let's
say mydnet1 contains example.net: 10.0.2.22. Edgemanage
tests 10.0.2.22 as it would any other edge but never selects it for
what edgemanage considers to be "liveness". If
10.0.2.22 is in a passing state, a random edge from the current live
set is removed from example.net's configuration and 10.0.2.22 is
added. No other zones are affected and zone files are written as
normal.

Monitoring
--------

Straight forward Nagios-compliant checks are available in the
[nagios](nagios) directory. The checks are designed to use
nothing but the Python standard library the files that the
`edge_manage` script writes to the state and heath directories.

History
--------

Edgemanage was developed as a replacement for a few aspects of the
[Deflect](https://deflect.ca) project.

The name "edgemanage" is taken from the original Edgemanage tool in
the NodeJS [devopsjs](https://github.com/equalitie/devopsjs) toolset
by David Mason. For various reasons, Edgemanage2 is written in Python.

[^1]: Figures less than 60 seconds are actually outright forbidden as
it somewhat negates the purpose of the tool. Dry run mode can be used
to run more regularly with no file writing.

Python 2 to 3 upgrading process start around July of 2020, as Python 2
is no longer supported.
