#!/usr/bin/env python3

import unittest

from twimp import dice
from tests.fakes import ScriptedDice


class TestDiceFunctions(unittest.TestCase):
    def testRolling(self):
        d = dice.Dice(seed=1)
        """When we roll 10 dice, they all meet a target_number of 1."""
        self.assertEqual(d.RollWithTarget(target_number=1, number_of_dice=10), 10)
        """Conversely, rolling with an impossible target_number can't work."""
        self.assertEqual(d.RollWithTarget(target_number=11, number_of_dice=100), 0)
        """Rolling a sufficiently large number should produce a reasonable sum."""
        c = d.RollWithTarget(target_number=5, number_of_dice=1000)
        self.assertGreater(c, 550)
        self.assertLess(c, 650)

    def testSeedIsReproducible(self):
        """Two dice with the same seed roll the same sequence."""
        d1, d2 = dice.Dice(seed=42), dice.Dice(seed=42)
        self.assertEqual([d1.Roll() for _ in range(20)],
                         [d2.Roll() for _ in range(20)])

    def testAlteration(self):
        """A +1 alteration turns a roll of 6 into a hit on 7."""
        d = ScriptedDice([6, 6])
        self.assertEqual(d.RollWithTarget(7, 1), 0)
        self.assertEqual(d.RollWithTarget(7, 1, alteration=lambda y: y + 1), 1)


if __name__ == '__main__':
    unittest.main()
