# Importing this module gives individual tests an import context that works
# regardless of installation method.  See
# http://docs.python-guide.org/en/latest/writing/structure/

# Usage in a test module:
#from .context import edgemanage

import os
import sys

sys.path.insert(0, os.path.abspath('..'))

import edgemanage
