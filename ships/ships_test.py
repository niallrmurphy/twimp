#!/usr/bin/python

import os
import pprint
import unittest

import dice
import fleet
import ships

class TestDiceFunctions(unittest.TestCase):
  def testRolling(self):
    c = dice.Dice.RollWithTarget(target_number=1,
                                  number_of_dice=10,
                                  sides=10)
    self.assertEqual(c, 10)
    c = dice.Dice.RollWithTarget(target_number=11,
                                  number_of_dice=100,
                                  sides=10)
    self.assertEqual(c, 0)
    c = dice.Dice.RollWithTarget(target_number=5,
                                  number_of_dice=1000,
                                  sides=10)
    """This is kinda shitty"""
    self.assertGreater(c, 400)

class TestUnitCreation(unittest.TestCase):
  def setUp(self):
    pass

  def tearDown(self):
    pass

  def makeGenericCombatUnit(self):
    cu = ships.CombatUnit(edition = 4)
    self.assertEqual(cu.edition, 4)
    self.assertEqual(cu.damage, 0)

class TestShipsFunctions(unittest.TestCase):

  def setUp(self):
    pass

  def tearDown(self):
    pass

  def testCruiserMove(self):
    c = ships.Cruiser()
    self.assertEqual(c.movement, 2)

  def testCarrierCargoLimit4(self):
    c = ships.Carrier(edition = 4)
    self.assertEqual(c.edition, 4)
    """ 1-5 """
    for x in range(1,4):
      c.AddToCargo("x" + str(x))
    self.assertEqual(len(c.cargo), 3)
    self.assertEqual(c.AddToCargo("y"), True)
    self.assertEqual(c.AddToCargo("z"), False)
    self.assertEqual(len(c.cargo), 4)

  def testCarrierCargoLimit3(self):
    c = ships.Carrier(edition = 3)
    self.assertEqual(c.edition, 3)
    """ 1-5 """
    for x in range(1,6):
      c.AddToCargo("x")
    self.assertEqual(len(c.cargo), 5)
    self.assertEqual(c.AddToCargo("y"), True)
    self.assertEqual(c.AddToCargo("z"), False)
    self.assertEqual(len(c.cargo), 6)

class TestFleetFunctions(unittest.TestCase):

  def setUp(self):
    self.f1 = {'Cruiser': 3, 'Destroyer': 7, 'Fighter': 4}
    self.f2 = {'Destroyer': 5, 'WarSun': 1, 'Fighter': 4}
    self.f3 = {'Fighter': 1, 'Cruiser': 1, 'Destroyer': 1,
               'WarSun': 1, 'Dreadnought': 1}
    self.df1 = fleet.Fleet(self.f1, self.f2)
    self.df2 = fleet.Fleet(self.f3, {})

  def testFleetCreation(self):
    self.df1.InstantiateShipObjects(self.f1)
    self.assertIsNotNone(self.df1)

  def testFleetTotalDamage(self):
    self.df1.InstantiateShipObjects(self.f1)
    self.assertEqual(14, fleet.CalculateTotalDamageCapacity(self.df1.player_1_fleet))

  def testFleetAttackRound(self):
    self.f.player_1_fleet = self.f.InstantiateShipObjects(self.f1)
    self.f.player_2_fleet = self.f.InstantiateShipObjects(self.f2)
    self.assertGreater(self.f.AttackRound(), (0, 0))

  def testFleetDistributeDamageWipeout(self):
    self.f.player_1_fleet = self.f.InstantiateShipObjects(self.f1)
    self.f.player_2_fleet = self.f.InstantiateShipObjects(self.f2)
    self.assertEqual(self.f.DistributeMinimumDamage(self.f.player_1_fleet, 14), {})

  def testElementRemovalsSimple(self):
    self.f.player_1_fleet = self.f.InstantiateShipObjects(self.f1)
    self.f.player_2_fleet = self.f.InstantiateShipObjects(self.f2)
    damage_distributed = 0
    points = 3
    res = fleet.RemoveElems(damage_distributed,
                            self.f.player_1_fleet, 'Fighter', points)
    self.assertEqual(res, 3)
    self.assertEqual(len(self.f.player_1_fleet['Fighter']), 1)
    damage_distributed = 0
    points = 13
    res = fleet.RemoveElems(damage_distributed,
                            self.f.player_1_fleet, 'Cruiser', points)
    self.assertEqual(res, 3)
    self.assertEqual(len(self.f.player_1_fleet['Cruiser']), 0)

  def testFleetDistributeDamage(self):
    self.f.player_1_fleet = self.f.InstantiateShipObjects(self.f1)
    self.f.player_2_fleet = self.f.InstantiateShipObjects(self.f2)
    pprint.pprint(self.f.player_1_fleet)
    new_f = self.f.DistributeMinimumDamage(self.f.player_1_fleet, 4)
    self.assertEqual(new_f.get('Fighter'), [])
    pprint.pprint(self.f.player_1_fleet)
    new_f = self.f.DistributeMinimumDamage(self.f.player_1_fleet, 9)
    self.assertEqual(new_f.get('Destroyer'), [])
    #self.assertEqual(new_f.get('Cruiser'), [])
    pprint.pprint(new_f)

  def testFleetInOrderDistributeDamage(self):
    self.f2.player_1_fleet = self.f.InstantiateShipObjects(self.f3)
    pprint.pprint(self.f2.player_1_fleet)
    new_f = self.f2.DistributeMinimumDamage(self.f2.player_1_fleet, 1)
    self.assertEqual(new_f.get('Fighter'), [])
    new_f = self.f2.DistributeMinimumDamage(self.f2.player_1_fleet, 2)
    dr = new_f.get('Dreadnought')[0]
    self.assertEqual(dr.damage, 1)
    ws = new_f.get('WarSun')[0]
    self.assertEqual(ws.damage, 1)
    new_f = self.f2.DistributeMinimumDamage(self.f2.player_1_fleet, 1)
    pprint.pprint(new_f)

if __name__ == '__main__':
  unittest.main()
