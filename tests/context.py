# Importing this module gives individual tests an import context that works
# regardless of installation method.  See
# http://docs.python-guide.org/en/latest/writing/structure/

# Usage in a test module:
# from .context import edgemanage

from __future__ import absolute_import
import os
import sys

sys.path.insert(0, os.path.abspath('..'))

import edgemanage  # flake8: noqa
