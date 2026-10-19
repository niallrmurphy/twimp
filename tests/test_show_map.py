#!/usr/bin/env python3

import contextlib
import io
import unittest

from twimp import show_map


def Run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        show_map.main(list(argv))
    return out.getvalue()


class TestShowMap(unittest.TestCase):
    def testShowsSampleMap(self):
        text = Run()
        self.assertIn('18', text)
        self.assertIn('41G', text)

    def testReachable(self):
        text = Run('--from', '22', '--move', '1')
        self.assertIn('(22)', text)
        self.assertIn('reaches 7 systems', text)
        self.assertIn('22 > 41G > 30  (1 gravity rift roll)', text)

    def testAsteroids(self):
        self.assertIn('[44A]', Run('--from', '22', '--move', '1', '--asteroids'))

    def testShowResources(self):
        text = Run('--show-resources')
        # Totals on the map: New Albion 1/1 + Starpoint 3/1.
        self.assertIn('27 4/2', text)
        self.assertIn('18 1/6', text)
        # Systems without planets keep their plain label.
        self.assertIn('41G', text)
        self.assertNotIn('41G 0/0', text)
        self.assertIn('Starpoint    3/1  hazardous', text)
        self.assertIn('Meer         0/4  hazardous, warfare', text)

    def testShowResourcesWithReach(self):
        text = Run('--from', '27', '--move', '1', '--show_resources')
        self.assertIn('(27 4/2)', text)
        self.assertIn('[20 2/2]', text)
        self.assertIn('Planets (resources/influence):', text)


if __name__ == '__main__':
    unittest.main()
