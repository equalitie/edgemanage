#!/usr/bin/env python

from __future__ import absolute_import
import unittest
import tempfile
import shutil
import time

from .context import edgemanage
from six.moves import range

TEST_EDGE = "testedge1"
TEST_FETCH_HISTORY = 4
# Patch edgestate's import of const
edgemanage.edgestate.FETCH_HISTORY = TEST_FETCH_HISTORY


class EdgeStateTemplate(unittest.TestCase):
    """
    Sub-classable test to handle state file generation and cleanup
    """
    def _make_store(self):
        self.store_dir = tempfile.mkdtemp()
        a = edgemanage.edgestate.EdgeState(TEST_EDGE, self.store_dir)
        return a

    def tearDown(self):
        shutil.rmtree(self.store_dir)


class EdgeStateTest(EdgeStateTemplate):

    # TODO load test JSON file to ensure object creation
    def testStoreAverage(self):
        a = self._make_store()

        for i in range(4):
            a.add_value(2)

        average = a.current_average()
        self.assertEqual(average, 2)

    def testStoreRotation(self):
        a = self._make_store()

        for i in range(TEST_FETCH_HISTORY+1):
            a.add_value(2)
            time.sleep(0.01)

        self.assertEqual(len(a), TEST_FETCH_HISTORY)

if __name__ == '__main__':
    unittest.main()
