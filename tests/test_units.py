#!/usr/bin/env python3

import unittest

from twimp import units
from twimp.units import Ability, Unit, UnitType
from tests.fakes import ScriptedDice


class TestUnitStats(unittest.TestCase):
    def testEveryUnitTypeHasStats(self):
        for unit_type in UnitType:
            self.assertIn(unit_type, units.UNIT_STATS)

    def test4eReferenceValues(self):
        """Spot-check the table against the 4e faction sheet."""
        s = units.UNIT_STATS
        self.assertEqual((s[UnitType.CARRIER].combat, s[UnitType.CARRIER].move,
                          s[UnitType.CARRIER].capacity), (9, 1, 4))
        self.assertEqual(s[UnitType.DREADNOUGHT].move, 1)
        self.assertEqual(s[UnitType.DREADNOUGHT].capacity, 1)
        self.assertEqual(s[UnitType.DREADNOUGHT].bombardment, Ability(5, 1))
        self.assertEqual(s[UnitType.WARSUN].capacity, 6)
        self.assertEqual(s[UnitType.WARSUN].bombardment, Ability(3, 3))
        self.assertEqual(s[UnitType.DESTROYER].anti_fighter_barrage,
                         Ability(9, 2))
        self.assertEqual(s[UnitType.INFANTRY].combat, 8)
        self.assertIsNone(s[UnitType.FIGHTER].plastic_limit)
        self.assertIsNone(s[UnitType.INFANTRY].plastic_limit)
        self.assertEqual(s[UnitType.SPACEDOCK].plastic_limit, 3)

    def testFighterUnitCost(self):
        """Fighters cost 1 for 2."""
        self.assertEqual(Unit(UnitType.FIGHTER).production_cost, 0.5)

    def testCategories(self):
        self.assertTrue(Unit(UnitType.CRUISER).IsShip())
        self.assertTrue(Unit(UnitType.INFANTRY).IsGroundForce())
        self.assertTrue(Unit(UnitType.PDS).IsStructure())
        self.assertTrue(Unit(UnitType.SPACEDOCK).IsStructure())


class TestUnitFunctions(unittest.TestCase):
    def testRejectsNonUnitType(self):
        with self.assertRaises(ValueError):
            Unit('Cruiser')

    def testCruiserMove(self):
        self.assertEqual(Unit(UnitType.CRUISER).movement, 2)

    def testFlagshipConstructs(self):
        """Regression: Flagship used to call super(Fighter, ...)."""
        self.assertEqual(Unit(UnitType.FLAGSHIP).max_produceable, 1)

    def testCarrierCargoLimit(self):
        """Test we can't overload a carrier."""
        c = Unit(UnitType.CARRIER)
        for x in range(3):
            c.AddToCargo("x" + str(x))
        self.assertEqual(len(c.cargo), 3)
        self.assertTrue(c.AddToCargo("y"))
        self.assertFalse(c.AddToCargo("z"))
        self.assertEqual(len(c.cargo), 4)

    def testRemoveFromCargo(self):
        """Regression: RemoveFromCargo used to call a nonexistent pop()."""
        c = Unit(UnitType.CARRIER)
        c.AddToCargo("a")
        c.AddToCargo("b")
        self.assertEqual(c.RemoveFromCargo(), "b")
        self.assertEqual(c.cargo, ["a"])

    def testDreadnoughtGenerateHits(self):
        """Regression: Dreadnought used to refer to an undefined Dice."""
        self.assertEqual(Unit(UnitType.DREADNOUGHT).GenerateHits(ScriptedDice([5])), 1)
        self.assertEqual(Unit(UnitType.DREADNOUGHT).GenerateHits(ScriptedDice([4])), 0)

    def testWarSunRollsThreeDice(self):
        self.assertEqual(Unit(UnitType.WARSUN).GenerateHits(ScriptedDice([3, 2, 10])), 2)

    def testDestroyerAntiFighterBarrage(self):
        """Regression: AFB used to refer to an undefined Dice."""
        d = Unit(UnitType.DESTROYER)
        self.assertTrue(d.CanGenerateAntiFighterBarrage())
        self.assertEqual(d.GenerateAntiFighterBarrage(ScriptedDice([9, 8])), 1)

    def testNonCombatUnitsDontHit(self):
        self.assertEqual(Unit(UnitType.PDS).GenerateHits(ScriptedDice([])), 0)
        self.assertEqual(Unit(UnitType.PDS).GenerateSpaceCannon(ScriptedDice([6])), 1)

    def testSustainDamage(self):
        d = Unit(UnitType.DREADNOUGHT)
        self.assertEqual(d.CanHandleDamage(), 2)
        self.assertEqual(d.ReceiveHits(1), 1)
        self.assertTrue(d.IsDamaged())
        self.assertEqual(d.CanHandleDamage(), 1)
        self.assertEqual(d.ReceiveHits(1), 0)

    def testRepair(self):
        d = Unit(UnitType.WARSUN)
        d.ReceiveHits(1)
        d.Repair()
        self.assertFalse(d.IsDamaged())
        self.assertEqual(d.CanHandleDamage(), 2)

    def testSingleHitDestroysCruiser(self):
        self.assertEqual(Unit(UnitType.CRUISER).ReceiveHits(1), 0)


if __name__ == '__main__':
    unittest.main()
