#!/usr/bin/env python3

import contextlib
import io
import unittest

from twimp import simulate_invasion as si
from twimp.units import UnitType
from tests.fakes import ScriptedDice


class TestSimulateInvasion(unittest.TestCase):
    def testParseForces(self):
        ships, ground, planet = si.ParseForces('warsun', 'infantry=3', 'infantry,pds')
        self.assertEqual(ships, {UnitType.WARSUN: 1})
        self.assertEqual(ground, {UnitType.INFANTRY: 3})
        self.assertEqual(planet, {UnitType.INFANTRY: 1, UnitType.PDS: 1})

    def testParseForcesRejectsWrongKinds(self):
        for args in (('infantry', 'infantry', ''),      # infantry isn't a ship
                     ('', 'cruiser', ''),                # can't land a cruiser
                     ('', 'infantry', 'destroyer')):     # ships aren't on planets
            with self.assertRaises(ValueError):
                si.ParseForces(*args)

    def testOutcomes(self):
        ground = {UnitType.INFANTRY: 1}
        defenders = {UnitType.INFANTRY: 1}
        self.assertEqual(si.RunOnce({}, ground, {}, ScriptedDice([])), (si.CAPTURED, 1))
        self.assertEqual(si.RunOnce({}, ground, defenders, ScriptedDice([8, 1])),
                         (si.CAPTURED, 1))
        self.assertEqual(si.RunOnce({}, ground, defenders, ScriptedDice([1, 8])),
                         (si.HELD, 0))
        self.assertEqual(si.RunOnce({}, ground, defenders, ScriptedDice([8, 8])),
                         (si.WIPED, 0))

    def testSimulateIsReproducible(self):
        args = ({UnitType.DREADNOUGHT: 1}, {UnitType.INFANTRY: 3},
                {UnitType.INFANTRY: 2, UnitType.PDS: 1}, 300)
        first = si.Simulate(*args, seed=5)
        self.assertEqual(first, si.Simulate(*args, seed=5))
        self.assertEqual(sum(first[0].values()), 300)

    def testWarSunBeatsShieldedPlanet(self):
        """The war sun's bombardment ignores the PDS shield, so it should
        do much better than a dreadnought against the same planet."""
        ground = {UnitType.INFANTRY: 3}
        planet = {UnitType.INFANTRY: 2, UnitType.PDS: 1}
        with_warsun, _ = si.Simulate({UnitType.WARSUN: 1}, ground, planet, 500, seed=1)
        with_dread, _ = si.Simulate({UnitType.DREADNOUGHT: 1}, ground, planet, 500, seed=1)
        self.assertGreater(with_warsun[si.CAPTURED], with_dread[si.CAPTURED] + 100)

    def testMain(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            si.main(['--ground', 'infantry=2', '--planet', 'infantry', '-n', '50',
                     '--seed', '1'])
        self.assertIn('captured', out.getvalue())


if __name__ == '__main__':
    unittest.main()
