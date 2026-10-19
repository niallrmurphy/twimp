#!/usr/bin/env python3

import contextlib
import io
import unittest

from twimp import simulate
from twimp.units import UnitType


class TestSimulate(unittest.TestCase):
    def testParseForce(self):
        self.assertEqual(simulate.ParseForce('dreadnought=2, war_sun,carrier'),
                         {UnitType.DREADNOUGHT: 2, UnitType.WARSUN: 1,
                          UnitType.CARRIER: 1})

    def testParseForceRejectsBadInput(self):
        for spec in ('pds', 'infantry=2', 'starbase'):
            with self.assertRaises(ValueError):
                simulate.ParseForce(spec)

    def testSimulateIsReproducible(self):
        a = simulate.ParseForce('dreadnought=2')
        d = simulate.ParseForce('destroyer=4')
        first = simulate.Simulate(a, d, 200, seed=3)
        self.assertEqual(first, simulate.Simulate(a, d, 200, seed=3))
        self.assertEqual(sum(first[0].values()), 200)

    def testOverwhelmingForceWins(self):
        outcomes, _ = simulate.Simulate(simulate.ParseForce('warsun=2'),
                                        simulate.ParseForce('fighter'), 200, seed=1)
        self.assertGreater(outcomes['attacker'], 190)

    def testMain(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            simulate.main(['cruiser', 'cruiser', '-n', '50', '--seed', '1'])
        self.assertIn('attacker wins', out.getvalue())


if __name__ == '__main__':
    unittest.main()
