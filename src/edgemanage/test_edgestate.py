#!/usr/bin/env python

import unittest
import tempfile
import time

import edgestate

TEST_EDGE = "testedge1"
TEST_FETCH_HISTORY = 4
# Patch edgestate's import of const
edgestate.FETCH_HISTORY = TEST_FETCH_HISTORY

class EdgeStateTest(unittest.TestCase):

    # TODO load test JSON file to ensure object creation

    @staticmethod
    def _make_store():
        store_dir = tempfile.mkdtemp()
        a = edgestate.EdgeState(TEST_EDGE, store_dir)
        return a

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
