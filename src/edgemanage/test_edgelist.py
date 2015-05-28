#!/usr/bin/env python

import unittest
from edgelist import EdgeList

TEST_DOMAIN = "fakesite.deflect.ca"

class EdgeListTest(unittest.TestCase):

    def test_reject_bad_NS(self):
        a = EdgeList()
        self.assertRaises(Exception, a.generate_zone, ("equalit.ie", "test_data", {
            "ns_records": ["adns1.easydns.com",
                           "adns2.easydns.com"]
        }))

    def test_set_edge_live(self):
        a = EdgeList()
        a.add_edge("test1")
        a.set_edge_live("test1")
        self.assertTrue(a.edges["test1"]["live"])

    def test_len(self):
        a = EdgeList()
        a.add_edge("test1")
        a.add_edge("test2")
        a.add_edge("test3")
        self.assertEqual(len(a), 3)

    def test_liveness_operations(self):
        a = EdgeList()
        a.add_edge("test1", live=True)
        a.add_edge("test2")
        a.add_edge("test3")
        a.set_edge_live("test2")
        self.assertEqual(a.get_live_count(), 2)
        self.assertTrue(a.is_live("test1"))

    def test_state_operations(self):
        a = EdgeList()
        a.add_edge("test1")
        a.add_edge("test2", state="pass")
        a.add_edge("test3", state="pass")
        a.add_edge("test4", state="fail")
        # invalid state - edgelist don't care.
        a.add_edge("test5", state="satan")
        a.add_edge("test6", state="pass")

        self.assertEqual(a.get_state_stats(), {'fail': 1, None: 1, 'satan': 1, 'pass': 3})
        self.assertTrue(a.set_live_by_state("pass", 2))
        self.assertEqual(a.get_live_count(), 2)
        self.assertEqual(len(a.get_edges("pass")), 3)

    def test_generate_zonefile(self):
        a = EdgeList()
        a.add_edge("example.com")
        a.set_edge_live("example.com")
        new_zone = a.generate_zone("test.com", "test_data", {"ns_records": ["adns1.easydns.com."],
                                                             "soa_mailbox": "test.derp.com",
                                                             "soa_nameserver": "derpderpderp.com"
                                                         },
                                   serial_number=1234)
        with open("test_data/test.com.output") as known_zone_f:
            known_zone = known_zone_f.read()
        self.assertEqual(known_zone, new_zone)

if __name__ == '__main__':
    unittest.main()
