#!/usr/bin/env python3

from twimp import board
from twimp import hexes
from twimp.units import Unit, UnitType
import unittest

class TestTileData(unittest.TestCase):

  def testAllBaseGameTiles(self):
    self.assertEqual(sorted(int(t) for t in board.TileData()), list(range(1, 51)))

  def testPlanetTotals(self):
    """58 planets in tiles 1-50, Mecatol Rex included."""
    planets = [p for t in board.TileData().values() for p in t.get('planets', [])]
    self.assertEqual(len(planets), 58)

  def testMakeSystem(self):
    lodor = board.MakeSystem(26)
    self.assertEqual(lodor.wormholes, {'alpha'})
    planet = lodor.planets[0]
    self.assertEqual((planet.name, planet.resources, planet.influence, planet.trait),
                     ('Lodor', 3, 1, 'cultural'))
    meer = board.MakeSystem('37').planets[1]
    self.assertEqual((meer.name, meer.tech_specialty), ('Meer', 'warfare'))
    self.assertEqual(board.MakeSystem('43').anomaly, board.Anomaly.SUPERNOVA)
    self.assertEqual(board.MakeSystem('1').home, 'The Federation of Sol')
    self.assertEqual(board.MakeSystem('18').planets[0].influence, 6)

  def testMakeSystemGivesFreshPlanets(self):
    self.assertIsNot(board.MakeSystem(26).planets[0], board.MakeSystem(26).planets[0])

  def testUnknownTile(self):
    with self.assertRaises(board.CannotPerformException):
      board.MakeSystem(83)

  def testLabels(self):
    self.assertEqual(board.MakeSystem(26).Label(), '26a')
    self.assertEqual(board.MakeSystem(41).Label(), '41G')
    self.assertEqual(board.MakeSystem(1).Label(), '1H')
    self.assertEqual(board.MakeSystem(18).Label(), '18')


class TestSystem(unittest.TestCase):

  def testShips(self):
    system = board.MakeSystem(46)
    cruiser, infantry = Unit(UnitType.CRUISER), Unit(UnitType.INFANTRY)
    system.AddUnit('red', cruiser)
    system.AddUnit('red', infantry)
    system.AddUnit('blue', Unit(UnitType.INFANTRY))
    self.assertEqual(system.ShipsOf('red'), [cruiser])
    self.assertEqual(system.PlayersWithShips(), ['red'])
    self.assertTrue(system.HasOtherPlayersShips('blue'))
    # Blue only has a ground force in space, which isn't a ship.
    self.assertFalse(system.HasOtherPlayersShips('red'))


class TestBoard(unittest.TestCase):

  def setUp(self):
    self.board = board.Board.FromMapString(board.SAMPLE_MAP)

  def testSampleMap(self):
    self.assertEqual(len(self.board.systems), 37)
    self.assertEqual(self.board.SystemAt(hexes.CENTER).tile_id, '18')
    # Ring 1 starts directly north of Mecatol Rex.
    self.assertEqual(self.board.Find('19'), hexes.NORTH)
    self.assertEqual(self.board.Find('26'), hexes.NORTH_EAST)
    # Home systems are every third tile of the outer ring.
    homes = [self.board.SystemAt(c).home is not None for c in hexes.Ring(3)]
    self.assertEqual(homes, [i % 3 == 0 for i in range(18)])

  def testExplicitCenterAndGaps(self):
    b = board.Board.FromMapString('{26} 0 19 0 0 0 0')
    self.assertEqual(b.SystemAt(hexes.CENTER).tile_id, '26')
    self.assertEqual(len(b.systems), 2)
    self.assertEqual(b.Find('19'), hexes.NORTH_EAST)

  def testUnknownTileInMap(self):
    with self.assertRaises(board.CannotPerformException):
      board.Board.FromMapString('19 26 83A2')

  def testAdjacentIncludesWormholes(self):
    lodor = self.board.Find('26')
    adjacent = self.board.Adjacent(lodor)
    self.assertEqual(len(adjacent), 7)
    self.assertIn(self.board.Find('39'), adjacent)
    # Alpha doesn't connect to beta.
    self.assertNotIn(self.board.Find('40'), adjacent)

  def testAdjacentSkipsEmptyPositions(self):
    corner = self.board.Find('1')
    self.assertEqual(len(self.board.Adjacent(corner)), 3)

  def testRender(self):
    text = self.board.Render(highlight={hexes.NORTH}, origin=hexes.CENTER)
    self.assertIn('(18)', text)
    self.assertIn('[19]', text)
    self.assertIn('43S', text)
    lines = text.splitlines()
    # 19 is two lines above 18, in the same column.
    row_18 = next(i for i, l in enumerate(lines) if '(18)' in l)
    self.assertIn('[19]', lines[row_18 - 2])
    self.assertEqual(lines[row_18].index('(18)') + 1, lines[row_18 - 2].index('[19]') + 1)


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
