#!/usr/bin/env python3

import unittest

from twimp import hexes
from twimp.hexes import Hex


class TestHexes(unittest.TestCase):
    def testNeighborsAreDistanceOne(self):
        h = Hex(2, -1)
        for n in hexes.Neighbors(h):
            self.assertEqual(hexes.Distance(h, n), 1)
        self.assertEqual(len(set(hexes.Neighbors(h))), 6)

    def testDistance(self):
        self.assertEqual(hexes.Distance(hexes.CENTER, Hex(0, -3)), 3)
        self.assertEqual(hexes.Distance(Hex(-1, 2), Hex(2, -1)), 3)
        self.assertEqual(hexes.Distance(Hex(1, 1), Hex(1, 1)), 0)

    def testRingOneIsNeighborsClockwiseFromNorth(self):
        self.assertEqual(hexes.Ring(1), hexes.Neighbors(hexes.CENTER))

    def testRings(self):
        for radius in range(1, 5):
            ring = hexes.Ring(radius)
            self.assertEqual(len(ring), 6 * radius)
            self.assertEqual(len(set(ring)), 6 * radius)
            self.assertTrue(all(hexes.Distance(hexes.CENTER, h) == radius for h in ring))
            self.assertEqual(ring[0], Hex(0, -radius))
            # Consecutive hexes are neighbours, and the ring closes.
            for a, b in zip(ring, ring[1:] + ring[:1]):
                self.assertEqual(hexes.Distance(a, b), 1)

    def testRingTwoGoesClockwise(self):
        self.assertEqual(hexes.Ring(2)[1], Hex(1, -2))

    def testSpiral(self):
        self.assertEqual(len(hexes.Spiral(3)), 37)
        self.assertEqual(hexes.Spiral(3)[0], hexes.CENTER)


if __name__ == '__main__':
    unittest.main()
