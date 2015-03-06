#!/usr/bin/env python

import unittest
import edgelist

TEST_DOMAIN = "fakesite.deflect.ca"

class EdgeListTest(unittest.TestCase):

    def testRejectBadNS(self):
        a = edgelist.EdgeList(TEST_DOMAIN)
        self.assertRaises(Exception, a.generate_zone, ("equalit.ie", "test_data", {
            "ns_records": ["adns1.easydns.com",
                           "adns2.easydns.com"]
        }))

    def testSetEdgeLive(self):
        a = edgelist.EdgeList(TEST_DOMAIN)
        a.add_edge("test1")
        a.make_active("test1")
        self.assertTrue(a.edges["test1"]["live"])

    def testGenerateZonefile(self):
        a = edgelist.EdgeList("deflect.ca")
        a.add_edge("chicago7")
        a.make_active("chicago7")
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
