# This module is useful for discovering programatically the module in which it
# resides. Place it in the same directory as code that needs to discover its
# location. In edgemanage it is used to help tests find their sample data-files
# regardless of the present working directory.
#
# http://stackoverflow.com/questions/2632199/how-do-i-get-the-path-of-the-current-executed-file-in-python
#
# Usage:
# import module_locator
# my_path = module_locator.module_path()


from __future__ import absolute_import
import os
import sys
import six


def we_are_frozen():
    # All of the modules are built-in to the interpreter, e.g., by py2exe
    return hasattr(sys, "frozen")


def module_path():
    # Return the absolute filesystem path to this module
    encoding = sys.getfilesystemencoding()
    if we_are_frozen():
        return os.path.dirname(six.text_type(sys.executable, encoding))
    return os.path.dirname(six.text_type(__file__, encoding))
