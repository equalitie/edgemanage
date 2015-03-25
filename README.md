edgemanage2
-------

Edgemanage is a tool for manging the HTTP availability of a cluster of
web servers via DNS. The machines tested are expected to be at risk of
large volumes of traffic, attack or other potential instability. If a
machine is found to be underperforming, it is replace by a more
performant host to ensure maximum availability.

Overview
=======

Edgemanage is a simple script and Python library designed to be run at
regular intervals, usually via crontab. The designed usecase was every
60 seconds but larger figures can be used[^1].

Edgemanage fetches an object from a lists of hosts over HTTP and uses
the time taken to retrieve the object to make decisions about which
hosts are healthiest. These hosts are then written to a zone file as A
records for the apex of a domain, in addition to additional records in
other files elsewhere.

The zone files that Edgemanage writes are created via Jinja templates,
with SOA and NS data defined in the configuration file and the output
format being bind-compliant. The per-domain records that are included
are plain ol' Bind style rules. Just don't include any SOA records.

Operation
=======

Edgemanage maintains a store of historial fetches per host and can
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
=======

For debugging, the use of the verbose mode is recommended. Using
verbose mode disable logging to syslog.

The dry run mode will only read the statefile and log/print the
decisions that would be made (use of the verbose switch is
recommended).

Configuration
=======

The "object" that edgemanage focuses could be absolutely anything - in
testing the file that was used was a simple text file. The only
concern is that an object that takes a long time runs the risk of
coming close to theoretical fetch times in slow situation, thereby
potentially interrupting sequential runs.

See the `edgemanage.yaml` file for documentation of the configuration
options.

History
=======

Edgemanage was developed as a replacement for a few aspects of the
[Deflect](https://deflect.ca) project.

The name "edgemanage" is taken from the original Edgemanage tool in
the NodeJS [devopsjs](https://github.com/equalitie/devopsjs) toolset
by David Mason. For various reasons, Edgemanage2 is written in Python.

[^1]: Figures less than 60 seconds are actually outright forbidden as
it somewhat negates the purpose of the tool. Dry run mode can be used
to run more regularly with no file writing.
