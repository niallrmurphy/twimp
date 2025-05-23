#!/usr/bin/env python3

import os
import pprint
import unittest

import dice
import fleet
import ships

from ships import ShipType

class TestDiceFunctions(unittest.TestCase):
    def testRolling(self):
        """When we roll 10 dice, they all exceed target_number of 1."""
        c = dice.Dice.RollWithTarget(target_number=1,
                                     number_of_dice=10,
                                     sides=10)
        self.assertEqual(c, 10)
        """Conversely, rolling with an impossible target_number can't work."""
        c = dice.Dice.RollWithTarget(target_number=11,
                                     number_of_dice=100,
                                     sides=10)
        self.assertEqual(c, 0)
        """Rolling a sufficiently large number should produce a reasonable sum."""
        c = dice.Dice.RollWithTarget(target_number=5,
                                     number_of_dice=1000,
                                     sides=10)
        """This is bad but tolerable for now."""
        self.assertGreater(c, 400)


class TestUnitCreation(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def makeGenericCombatUnit(self):
        cu = ships.CombatUnit(edition=4)
        self.assertEqual(cu.edition, 4)
        self.assertEqual(cu.damage, 0)


class TestShipsFunctions(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testCruiserMove(self):
        """Test a basic instantiaion property of a ship."""
        c = ships.Cruiser()
        self.assertEqual(c.movement, 2)

    def testCarrierCargoLimit4(self):
        """For the 4th edition, test we can't overload a carrier."""
        c = ships.Carrier(edition=4)
        self.assertEqual(c.edition, 4)
        """Trickily, python's range operator excludes the last number."""
        for x in range(1, 4):
            c.AddToCargo("x" + str(x))
        self.assertEqual(len(c.cargo), 3)
        self.assertEqual(c.AddToCargo("y"), True)
        self.assertEqual(c.AddToCargo("z"), False)
        self.assertEqual(len(c.cargo), 4)

    def testCarrierCargoLimit3(self):
        """For the 3rd edition, test we can't overload a carrier."""
        c = ships.Carrier(edition=3)
        self.assertEqual(c.edition, 3)
        """Trickily, python's range operator excludes the last number."""
        for x in range(1, 6):
            c.AddToCargo("x")
        self.assertEqual(len(c.cargo), 5)
        self.assertEqual(c.AddToCargo("y"), True)
        self.assertEqual(c.AddToCargo("z"), False)
        self.assertEqual(len(c.cargo), 6)


class TestFleetFunctions(unittest.TestCase):
    def setUp(self):
        # Static fleets by name
        self.sfbn1 = {'Cruiser': 3, 'Destroyer': 7, 'Fighter': 4}
        self.sfbn2 = {'Destroyer': 5, 'WarSun': 1, 'Fighter': 4}
        self.sfbn3 = {'Fighter': 1, 'Cruiser': 1, 'Destroyer': 1,
                      'WarSun': 1, 'Dreadnought': 1}
        self.sfbe1 = {ShipType.CRUISER: 3, ShipType.DESTROYER: 7, ShipType.FIGHTER: 4}
        self.sfbe2 = {ShipType.DESTROYER: 5, ShipType.WARSUN: 1, ShipType.FIGHTER: 4}
        self.sfbe3 = {ShipType.FIGHTER: 1, ShipType.CRUISER: 1, ShipType.DESTROYER: 1,
                      ShipType.WARSUN: 1, ShipType.DREADNOUGHT: 1}
        # Instantiated fleets
        self.if1 = fleet.Fleet(self.sfbn1, self.sfbn2)
        self.if2 = fleet.Fleet(self.sfbn3, {})
        # Ship objects
        self.if1.player_1_fleet = self.if1.InstantiateShipObjects(self.sfbn1)
        self.if1.player_2_fleet = self.if2.InstantiateShipObjects(self.sfbn2)

    def testCountShipsOfType(self):
        """We should be able to count how many ships of what type in a fleet."""
        self.assertEqual((7, 5), self.if1.CountShipsOfType('Destroyer'))

    def testAddShipsToFleet(self):
        """Starting with a blank fleet, simulate construction with budget and produce limits."""
        self.if1 = fleet.Fleet({}, {}, False)
        self.if2 = fleet.Fleet({}, {}, False, budget=5)
        # Try to add something to the third and None-th fleet, which don't exist.
        self.assertEqual(False, self.if1.AddShipToFleet('Fighter', 3))
        self.assertEqual(False, self.if1.AddShipToFleet('Fighter'))
        # Try to add something to a zero-budget fleet (failure)
        self.assertEqual(False, self.if1.AddShipToFleet('Fighter', 1))
        # Try to add something to a 2-budget fleet (success under ignore_dock)
        self.assertTrue(self.if2.AddShipToFleet('Fighter', 1))
        # Try to add a larger than 5 thing to a 5-budget fleet (failure)
        self.assertFalse(self.if2.AddShipToFleet('WarSun', 1))
        # Try to build something when ignore_dock is False and no dock exists; fail
        self.assertFalse(self.if2.AddShipToFleet('Carrier', ignore_dock=False))
        # Try to build a dock when ignore_dock is False and no dock exists; succeed
        self.assertTrue(self.if2.AddShipToFleet('SpaceDock', player_fleet=1, ignore_dock=False))
        # Can only add fighters when fleet has capacity for them
        self.assertEqual((1,0), self.if2.CountShipsOfType('Fighter'))

    def testFleetTotalDamage(self):
        """The first fleet should be able to soak 14 hits."""
        self.assertEqual(14, fleet.CalculateTotalDamageCapacity(self.if1.player_1_fleet))

    def testFleetAttackRound(self):
        """Actual fleets should do more damage in an attack round than 0 each."""
        self.assertGreater(self.if1.AttackRound(), (0, 0))

    def testFleetDistributeDamageWipeout(self):
        """After we distribute more damage than fleet has hits, we should have no fleet left."""
        self.assertEqual(self.if1.DistributeMinimumDamage(self.if1.player_1_fleet, 14), {})

    def testApplyDamangeRemovingShips(self):
        """We should remove ships from a fleet, given sufficient damage."""
        self.if1.player_1_fleet = self.if1.InstantiateShipObjects(self.sfbn1)
        self.if2.player_2_fleet = self.if2.InstantiateShipObjects(self.sfbn2)
        damage_distributed = 0
        points = 3
        res = fleet.ApplyDamageRemovingShips(damage_distributed,
                                             self.if1.player_1_fleet,
                                             'Fighter', points)
        # When we apply 3 damage to a fleet containing 4 fighters,
        # 3 should have gone and one should be left
        self.assertEqual(res, 3)
        self.assertEqual(len(self.if1.player_1_fleet['Fighter']), 1)
        damage_distributed = 0
        points = 13
        res = fleet.ApplyDamageRemovingShips(damage_distributed,
                                             self.if1.player_1_fleet,
                                             'Cruiser', points)
        self.assertEqual(res, 3)
        self.assertEqual(len(self.if1.player_1_fleet['Cruiser']), 0)

    def testFleetDistributeDamage(self):
        new_f = self.if1.DistributeMinimumDamage(self.if1.player_1_fleet, 4)
        self.assertEqual(new_f.get('Fighter'), [])
        new_f = self.if1.DistributeMinimumDamage(self.if1.player_1_fleet, 9)
        self.assertEqual(new_f.get('Destroyer'), [])
        self.assertEqual(new_f.get('Cruiser'), [])

    def testFleetInOrderDistributeDamage(self):
        self.if1.player_1_fleet = self.if1.InstantiateShipObjects(self.sfbn3)
        new_f = self.if1.DistributeMinimumDamage(self.if1.player_1_fleet, 1)
        self.assertEqual(new_f.get('Fighter'), [])
        new_f = self.if1.DistributeMinimumDamage(self.if1.player_1_fleet, 2)
        dr = new_f.get('Dreadnought')[0]
        self.assertEqual(dr.damage, 1)
        ws = new_f.get('WarSun')[0]
        self.assertEqual(ws.damage, 1)
        new_f = self.if1.DistributeMinimumDamage(self.if1.player_1_fleet, 1)

    def testIon(self):
        pass


if __name__ == '__main__':
    unittest.main()
