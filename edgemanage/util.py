"""
Global utility functions
"""

from __future__ import absolute_import
import os
import logging
import tempfile as tmp
import fcntl
from contextlib import contextmanager


class DnetLogFilter(logging.Filter):
    """Stamp every log record with the dnet the current run operates on.

    Attached to handlers rather than to a logger so that records
    propagated from library loggers (requests, urllib3) are tagged too -
    a logger's filters don't apply to records it only propagates.
    """

    def __init__(self, dnet):
        logging.Filter.__init__(self)
        self.dnet = dnet if dnet else "-"

    def filter(self, record):
        record.dnet = self.dnet
        return True


def acquire_lock(lockfile):
    # lockfile should be an opened file in mode w

    try:
        fcntl.lockf(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        return False

    return True


@contextmanager
def tempfile(suffix='', dir=None):
    """ Context for temporary file.

    Will find a free temporary filename upon entering
    and will try to delete the file on leaving, even in case of an exception.

    Parameters
    ----------
    suffix : string
        optional file suffix
    dir : string
        optional directory to save temporary file in
    """

    tf = tmp.NamedTemporaryFile(delete=False, suffix=suffix, dir=dir)
    tf.file.close()
    try:
        yield tf.name
    finally:
        try:
            os.remove(tf.name)
        except OSError as e:
            if e.errno == 2:
                pass
            else:
                raise


@contextmanager
def open_atomic(filepath, fsync=False, **kwargs):
    """ Open temporary file object that atomically moves to destination upon
    exiting.

    Allows reading and writing to and from the same filename.

    The file will not be moved to destination in case of an exception.

    Parameters
    ----------
    filepath : string
        the file path to be opened
    fsync : bool
        whether to force write the file to disk
    **kwargs : mixed
        Any valid keyword arguments for :code:`open`
    """

    with tempfile(dir=os.path.dirname(os.path.abspath(filepath))) as tmppath:
        with open(tmppath, **kwargs) as file:
            try:
                yield file
            finally:
                if fsync:
                    file.flush()
                    os.fsync(file.fileno())
        os.rename(tmppath, filepath)
