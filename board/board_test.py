#!/usr/bin/python

import board
import unittest

class TestPlanetHexFunctions(unittest.TestCase):

  def setUp(self):
    self.planet1 = board.Planet("Xaalu", 3, 1)
    self.hex = board.Hex(wormholes=None,
                         planets=self.planet1,
                         trade_stations=None)

  def testContains(self):
    self.assertEqual(self.hex.Contains(), self.planet1)
   
  def testContainsPermanent(self):
    self.assertEqual(self.hex._ContainsPermanent(), self.planet2)
   
  def testContainsTemporary(self):
    self.assertEqual(self.hex._ContainsTemporary(), None)
   
  def testAddEntity(self):
    self.planet2 = board.Planet("Qaalude", 1, 3)
    self.hex.AddEntity(self.planet2)
    self.assertEqual(self.hex.Contains(), [self.planet1, self.planet2])

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
