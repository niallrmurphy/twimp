#!/usr/bin/python

import board
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

if __name__ == '__main__':
  unittest.main()
