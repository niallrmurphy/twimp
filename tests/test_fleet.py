#!/usr/bin/env python3

import unittest

from twimp import fleet
from twimp.units import UnitType
from tests.fakes import ScriptedDice

FIGHTER = UnitType.FIGHTER
CARRIER = UnitType.CARRIER
CRUISER = UnitType.CRUISER
DESTROYER = UnitType.DESTROYER
DREADNOUGHT = UnitType.DREADNOUGHT
WARSUN = UnitType.WARSUN


class TestFleetFunctions(unittest.TestCase):
    def setUp(self):
        self.sf1 = {CRUISER: 3, DESTROYER: 7, FIGHTER: 4}
        self.sf2 = {DESTROYER: 5, WARSUN: 1, FIGHTER: 4}
        self.sf3 = {FIGHTER: 1, CRUISER: 1, DESTROYER: 1,
                    WARSUN: 1, DREADNOUGHT: 1}
        self.if1 = fleet.Fleet(self.sf1, self.sf2)

    def testCountShipsOfType(self):
        """We should be able to count how many ships of what type in a fleet."""
        self.assertEqual((7, 5), self.if1.CountShipsOfType(DESTROYER))
        self.assertEqual((0, 0), self.if1.CountShipsOfType(CARRIER))

    def testAddShipsToFleet(self):
        """Starting with a blank fleet, simulate construction with budget and produce limits."""
        empty = fleet.Fleet({}, {}, False)
        f = fleet.Fleet({}, {}, False, budget=5)
        # Try to add something to the zeroth, third and None-th fleet, which don't exist.
        self.assertFalse(empty.AddShipToFleet(FIGHTER, 0))
        self.assertFalse(empty.AddShipToFleet(FIGHTER, 3))
        self.assertFalse(empty.AddShipToFleet(FIGHTER))
        # Try to add something to a zero-budget fleet (failure)
        self.assertFalse(empty.AddShipToFleet(FIGHTER, 1))
        # Try to add something to a 5-budget fleet (success under ignore_dock)
        self.assertTrue(f.AddShipToFleet(FIGHTER, 1))
        self.assertEqual(f.budget, 4.5)
        # Try to add a larger than 5 thing to a 5-budget fleet (failure)
        self.assertFalse(f.AddShipToFleet(WARSUN, 1))
        # Try to build something when ignore_dock is False and no dock exists; fail
        self.assertFalse(f.AddShipToFleet(CARRIER, 1, ignore_dock=False))
        self.assertEqual((1, 0), f.CountShipsOfType(FIGHTER))

    def testAddShipRespectsPlasticLimit(self):
        f = fleet.Fleet({WARSUN: 2}, {}, budget=100)
        self.assertFalse(f.AddShipToFleet(WARSUN, 1))
        self.assertTrue(f.AddShipToFleet(WARSUN, 2))
        self.assertEqual(f.budget, 88)

    def testAddShipNeedsDock(self):
        f = fleet.Fleet({UnitType.SPACEDOCK: 1}, {}, budget=10)
        self.assertTrue(f.AddShipToFleet(CARRIER, 1, ignore_dock=False))
        self.assertFalse(f.AddShipToFleet(CARRIER, 2, ignore_dock=False))

    def testFleetTotalDamage(self):
        """The first fleet should be able to soak 14 hits; sustain counts double."""
        self.assertEqual(14, fleet.CalculateTotalDamageCapacity(self.if1.player_1_fleet))
        self.assertEqual(11, fleet.CalculateTotalDamageCapacity(self.if1.player_2_fleet))

    def testStructuresDontAbsorbHits(self):
        f = fleet.Fleet({CRUISER: 1, UnitType.PDS: 2, UnitType.SPACEDOCK: 1}, {})
        self.assertEqual(1, fleet.CalculateTotalDamageCapacity(f.player_1_fleet))

    def testFleetAttackRound(self):
        """With every die a 10, each ship hits once per combat die."""
        f = fleet.Fleet(self.sf1, self.sf2, dice=ScriptedDice([10] * 30))
        self.assertEqual(f.AttackRound(), (14, 12))

    def testFleetAttackRoundSeeded(self):
        """The same seed gives the same result."""
        from twimp import dice
        a = fleet.Fleet(self.sf1, self.sf2, dice=dice.Dice(seed=7)).AttackRound()
        b = fleet.Fleet(self.sf1, self.sf2, dice=dice.Dice(seed=7)).AttackRound()
        self.assertEqual(a, b)

    def testFleetDistributeDamageWipeout(self):
        """After we distribute more damage than fleet has hits, we should have no fleet left."""
        f1 = self.if1.player_1_fleet
        self.assertEqual(self.if1.DistributeMinimumDamage(f1, 14), {})
        self.assertEqual(self.if1.player_1_fleet, {})

    def testApplyHitsToType(self):
        """We should remove ships from a fleet, given sufficient damage."""
        f1 = self.if1.player_1_fleet
        # When we apply 3 damage to a fleet containing 4 fighters,
        # 3 should have gone and one should be left
        self.assertEqual(fleet.ApplyHitsToType(f1, FIGHTER, 3), 3)
        self.assertEqual(len(f1[FIGHTER]), 1)
        # More hits than cruisers: only 3 are assigned.
        self.assertEqual(fleet.ApplyHitsToType(f1, CRUISER, 13), 3)
        self.assertEqual(len(f1[CRUISER]), 0)

    def testApplyHitsSustainOnly(self):
        f = fleet.Fleet({DREADNOUGHT: 2}, {})
        f1 = f.player_1_fleet
        self.assertEqual(fleet.ApplyHitsToType(f1, DREADNOUGHT, 3, sustain_only=True), 2)
        self.assertEqual(len(f1[DREADNOUGHT]), 2)
        self.assertTrue(all(d.IsDamaged() for d in f1[DREADNOUGHT]))
        # Already damaged: no more sustain available.
        self.assertEqual(fleet.ApplyHitsToType(f1, DREADNOUGHT, 1, sustain_only=True), 0)

    def testFleetDistributeDamage(self):
        f1 = self.if1.player_1_fleet
        new_f = self.if1.DistributeMinimumDamage(f1, 4)
        self.assertEqual(new_f.get(FIGHTER), [])
        new_f = self.if1.DistributeMinimumDamage(f1, 9)
        self.assertEqual(new_f.get(DESTROYER), [])
        self.assertEqual(len(new_f.get(CRUISER)), 1)

    def testFleetInOrderDistributeDamage(self):
        f = fleet.Fleet(self.sf3, {})
        f1 = f.player_1_fleet
        new_f = f.DistributeMinimumDamage(f1, 1)
        self.assertEqual(new_f.get(FIGHTER), [])
        new_f = f.DistributeMinimumDamage(f1, 2)
        self.assertTrue(new_f.get(DREADNOUGHT)[0].IsDamaged())
        self.assertTrue(new_f.get(WARSUN)[0].IsDamaged())
        self.assertEqual(len(new_f.get(DESTROYER)), 1)
        new_f = f.DistributeMinimumDamage(f1, 1)
        self.assertEqual(new_f.get(DESTROYER), [])

    def testSustainedHitIsCounted(self):
        """Regression: a hit soaked by Sustain Damage used to go uncounted,
        so the same hit went on to destroy another ship as well."""
        f = fleet.Fleet({DREADNOUGHT: 1, DESTROYER: 1}, {})
        f1 = f.DistributeMinimumDamage(f.player_1_fleet, 1)
        self.assertTrue(f1[DREADNOUGHT][0].IsDamaged())
        self.assertEqual(len(f1[DESTROYER]), 1)

    def testCarriersCanBeHit(self):
        """Regression: carriers were missing from the damage order."""
        f = fleet.Fleet({CARRIER: 2, DREADNOUGHT: 1}, {})
        f1 = f.DistributeMinimumDamage(f.player_1_fleet, 2)
        self.assertTrue(f1[DREADNOUGHT][0].IsDamaged())
        self.assertEqual(len(f1[CARRIER]), 1)


if __name__ == '__main__':
    unittest.main()
