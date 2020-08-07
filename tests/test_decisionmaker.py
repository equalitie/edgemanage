#!/usr/bin/env python

from __future__ import absolute_import
import unittest

from .context import edgemanage

from .test_edgestate import EdgeStateTemplate

TEST_EDGE = "testedge1"
GOOD_ENOUGH = 1.0


class DecisionMakerTest(EdgeStateTemplate):

    def _get_failing_edge_state(self):
        es = self._make_store()
        es.add_value(edgemanage.const.FETCH_TIMEOUT)
        return es

    def _get_good_enough_edge_state(self):
        es = self._make_store()
        es.add_value(GOOD_ENOUGH/10)
        return es

    def _get_passing_edge_state(self):
        es = self._make_store()
        es.add_value(GOOD_ENOUGH*2)
        return es

    def _get_error_edge_state(self):
        es = self._make_store()
        es.add_value(edgemanage.const.FETCH_TIMEOUT)
        return es

    def test_error_state(self):
        es = self._get_error_edge_state()
        dm = edgemanage.decisionmaker.DecisionMaker()
        dm.add_edge_state(es)
        self.assertEqual(dm.check_threshold(GOOD_ENOUGH), {'fail': 1,
                                                           'pass_threshold': 0,
                                                           'pass_window': 0,
                                                           'pass_average': 0,
                                                           'pass': 0})

    def test_good_enough_state(self):
        es = self._get_good_enough_edge_state()
        dm = edgemanage.decisionmaker.DecisionMaker()
        dm.add_edge_state(es)
        self.assertEqual(dm.check_threshold(GOOD_ENOUGH), {'fail': 0,
                                                           'pass_threshold': 1,
                                                           'pass_window': 0,
                                                           'pass_average': 0,
                                                           'pass': 0})

    def test_passing_state(self):
        es = self._get_passing_edge_state()
        dm = edgemanage.decisionmaker.DecisionMaker()
        dm.add_edge_state(es)
        self.assertEqual(dm.check_threshold(GOOD_ENOUGH), {'fail': 0,
                                                           'pass_threshold': 0,
                                                           'pass_window': 0,
                                                           'pass_average': 0,
                                                           'pass': 1})

    def test_fail_state(self):
        es = self._get_failing_edge_state()
        dm = edgemanage.decisionmaker.DecisionMaker()
        dm.add_edge_state(es)
        self.assertEqual(dm.check_threshold(GOOD_ENOUGH), {'fail': 1,
                                                           'pass_threshold': 0,
                                                           'pass_window': 0,
                                                           'pass_average': 0,
                                                           'pass': 0})

    # def test_judgement(self):
    #    dm = DecisionMaker()
    #    passing_edge_state = _get_passing_edge_state()
    #    failing_edge_state = _get_failing_edge_state()


if __name__ == '__main__':
    unittest.main()
