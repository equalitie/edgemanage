#!/usr/bin/env python

import unittest
from .context import edgemanage

import tempfile
import subprocess


class UtilTest(unittest.TestCase):

    '''Tests for any utility functions'''

    def test_acquire_lock(self, do_subproc=False):
        '''Test for file locking, ensure we can and then can't lock a temporary file.
        '''
        temp_file = tempfile.mktemp()
        with open(temp_file, "w") as temp_file_f:

            self.assertTrue(edgemanage.util.acquire_lock(temp_file_f),
                            msg="Couldn't lock temporary file")

            # ayyyy lmao. Gotta have another process to get an flock
            # refused. I am a bad person and you should hate me.
            #
            # This is even more disgusting now tests are in a separate directory!
            test_lock_fail = subprocess.Popen([
                "python", "-c", (
                    "import os; import sys; "
                    "sys.path.insert(0, os.path.abspath('..')); "
                    "import edgemanage; "
                    "ret = edgemanage.util.acquire_lock(open('%s', 'w')); "
                    "sys.exit(0 if not ret else 1)"
                ) % temp_file])
            returncode = test_lock_fail.wait()
            self.assertEqual(returncode, 0,
                             msg="Could lock already locked temporary file")

if __name__ == '__main__':
    unittest.main()
