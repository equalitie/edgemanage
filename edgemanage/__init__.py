"""
Edgemanage is a tool for managing the HTTP availability of a cluster of
web servers via DNS. The machines tested are expected to be at risk of
large volumes of traffic, attack or other potential instability. If a
machine is found to be underperforming, it is replace by a more
performant host to ensure maximum availability.
"""

# flake8: noqa
from __future__ import absolute_import
from . import const
from . import util
from .edgetest import *
from .edgelist import EdgeList
from .edgestate import EdgeState
from .decisionmaker import DecisionMaker
from .statefile import StateFile
from .edgemanage import EdgeManage
