#!/usr/bin/env python3

from twimp import board
from twimp.units import Unit, UnitType
import unittest

class TestPlanetHexFunctions(unittest.TestCase):

  def setUp(self):
    self.planet1 = board.Planet("Xaalu", 3, 1)
    self.hex = board.Hex(wormholes=None,
                         planets=[self.planet1],
                         trade_stations=None)

  def testContains(self):
    self.assertEqual(self.hex.Contains(),
      {'trade_stations': None,
       'planets': [self.planet1],
       'wormholes': None})
   
  def testContainsPermanent(self):
    self.planet2 = board.Planet("Qaalude", 1, 3)
    self.hex.AddPlanet(self.planet2)
    self.assertEqual(self.hex._ContainsPermanent(),
      [self.planet1, self.planet2])
   
  def testContainsTemporary(self):
    self.assertEqual(self.hex._ContainsTemporary(), [])
   
  def testAddPlanet(self):
    self.planet2 = board.Planet("Qaalude", 1, 3)
    self.hex.AddPlanet(self.planet2)
    self.assertEqual(self.hex.Contains(),
      {'trade_stations': None,
       'planets': [self.planet1, self.planet2],
       'wormholes': None})

  def testConnectTo(self):
    pass
    
  def testCanConnectTo(self):
    pass
    
  def testCanPassThrough(self):
    pass
    
  def testNebula(self):
    pass
    
  def testAsteroid(self):
    pass
    
  def testSupernova(self):
    pass
    
  def testIon(self):
    pass

class TestPlanetControl(unittest.TestCase):
  def setUp(self):
    self.planet = board.Planet("Xaalu", 1, 1)

  def testStartsNeutral(self):
    self.assertTrue(self.planet.IsNeutral())
    self.assertTrue(self.planet.IsEmpty())

  def testGainControlExhausts(self):
    self.planet.GainControl("red")
    self.assertEqual(self.planet.controller, "red")
    self.assertTrue(self.planet.exhausted)
    self.planet.exhausted = False
    self.planet.GainControl("red")
    self.assertFalse(self.planet.exhausted)

  def testUnits(self):
    infantry, pds = Unit(UnitType.INFANTRY), Unit(UnitType.PDS)
    self.planet.AddUnit("red", infantry)
    self.planet.AddUnit("red", pds)
    self.assertEqual(self.planet.GroundForces("red"), [infantry])
    self.assertEqual(self.planet.Structures("red"), [pds])
    self.assertEqual(self.planet.OtherPlayers("blue"), ["red"])
    self.assertFalse(self.planet.IsEmpty())
    self.planet.RemoveUnits("red", [infantry])
    self.assertTrue(self.planet.IsEmpty())
    self.assertEqual(self.planet.UnitsOf("red"), [pds])


if __name__ == '__main__':
  unittest.main()
