#!/usr/bin/env python3

import unittest

from twimp import board as board_lib
from twimp import hexes
from twimp import movement
from twimp.hexes import Hex
from twimp.units import Unit, UnitType
from tests.fakes import ScriptedDice

C = hexes.CENTER
N = hexes.NORTH
N2 = Hex(0, -2)        # two north of the centre
N3 = Hex(0, -3)


def Board(tiles=None, radius=3):
    """A board of empty systems out to radius, with {coord: tile id} placed."""
    b = board_lib.Board()
    for coord in hexes.Spiral(radius):
        b.Place(coord, board_lib.MakeSystem(46))
    for coord, tile in (tiles or {}).items():
        b.Place(coord, board_lib.MakeSystem(tile))
    return b


def Reach(b, start, move, player='red', **kwargs):
    return movement.ReachableSystems(b, start, move, player, **kwargs)


class TestReachable(unittest.TestCase):
    def testOpenSpace(self):
        b = Board()
        self.assertEqual(set(Reach(b, C, 1)), set(hexes.Ring(1)))
        self.assertEqual(set(Reach(b, C, 2)), set(hexes.Ring(1) + hexes.Ring(2)))
        self.assertEqual(len(Reach(b, C, 3)), 36)

    def testZeroMove(self):
        self.assertEqual(Reach(Board(), C, 0), {})

    def testShortestPathsChosen(self):
        path = Reach(Board(), C, 3)[N3]
        self.assertEqual(path.systems, (C, N, N2, N3))
        self.assertEqual(path.rifts_exited, 0)

    def testEdgeOfBoard(self):
        """Positions with no system can't be moved through."""
        b = Board(radius=1)
        self.assertEqual(len(Reach(b, C, 3)), 6)

    def testSupernovaBlocks(self):
        b = Board({N: 43})
        reach = Reach(b, C, 2)
        self.assertNotIn(N, reach)
        # The only distance-2 route to N2 is through N.
        self.assertNotIn(N2, reach)
        # Going around takes 3 moves.
        self.assertEqual(len(Reach(b, C, 3)[N2].systems), 4)

    def testAsteroidFieldBlocksWithoutAntimass(self):
        b = Board({N: 44})
        self.assertNotIn(N, Reach(b, C, 2))
        self.assertNotIn(N2, Reach(b, C, 2))
        reach = Reach(b, C, 2, can_pass_asteroids=True)
        self.assertIn(N, reach)
        self.assertEqual(reach[N2].systems, (C, N, N2))

    def testNebulaIsADeadEnd(self):
        b = Board({N: 42})
        reach = Reach(b, C, 2)
        self.assertIn(N, reach)
        self.assertNotIn(N2, reach)

    def testStartingInNebulaMeansMoveOne(self):
        b = Board({C: 42})
        self.assertEqual(set(Reach(b, C, 3)), set(hexes.Ring(1)))

    def testGravityRiftGivesExtraMove(self):
        b = Board({N: 41})
        reach = Reach(b, C, 1)
        self.assertEqual(reach[N2].systems, (C, N, N2))
        self.assertEqual(reach[N2].rifts_exited, 1)
        # Neighbours of the rift that are also ours are reached directly.
        self.assertEqual(reach[hexes.NORTH_EAST].rifts_exited, 0)
        # Ending in the rift needs no roll.
        self.assertEqual(reach[N].rifts_exited, 0)

    def testStartingInGravityRift(self):
        b = Board({C: 41})
        self.assertEqual(set(Reach(b, C, 1)), set(hexes.Ring(1) + hexes.Ring(2)))
        self.assertEqual(Reach(b, C, 1)[N].rifts_exited, 1)

    def testSaferRoutePreferred(self):
        """With enough move, a destination is reached without the rift, even
        though the route through it is shorter."""
        b = Board({N: 41})
        # Every 2-move route to N2 goes through the rift at N.
        self.assertEqual(Reach(b, C, 2)[N2].rifts_exited, 1)
        safe = Reach(b, C, 3)[N2]
        self.assertEqual(safe.rifts_exited, 0)
        self.assertEqual(len(safe.systems), 4)

    def testEnemyShipsBlockPassingThrough(self):
        b = Board()
        b.SystemAt(N).AddUnit('blue', Unit(UnitType.DESTROYER))
        reach = Reach(b, C, 2)
        self.assertIn(N, reach)
        self.assertNotIn(N2, reach)

    def testOwnShipsAndEnemyGroundForcesDontBlock(self):
        b = Board()
        b.SystemAt(N).AddUnit('red', Unit(UnitType.DESTROYER))
        b.SystemAt(N).AddUnit('blue', Unit(UnitType.INFANTRY))
        self.assertEqual(Reach(b, C, 2)[N2].systems, (C, N, N2))

    def testWormholes(self):
        far_south = Hex(0, 3)
        b = Board({N3: 26, far_south: 39})
        reach = Reach(b, N3, 1)
        self.assertEqual(reach[far_south].systems, (N3, far_south))
        # Through the wormhole and one step beyond.
        self.assertIn(Hex(0, 2), Reach(b, N3, 2))

    def testDifferentWormholesDontConnect(self):
        far_south = Hex(0, 3)
        b = Board({N3: 26, far_south: 40})
        self.assertNotIn(far_south, Reach(b, N3, 1))


class TestUnitMovement(unittest.TestCase):
    def testMoveValuesByUnit(self):
        b = Board()
        counts = {t: len(movement.ReachableForUnit(b, C, Unit(t), 'red'))
                  for t in (UnitType.CARRIER, UnitType.CRUISER, UnitType.DREADNOUGHT,
                            UnitType.WARSUN, UnitType.FIGHTER, UnitType.INFANTRY,
                            UnitType.PDS)}
        self.assertEqual(counts, {UnitType.CARRIER: 6, UnitType.CRUISER: 18,
                                  UnitType.DREADNOUGHT: 6, UnitType.WARSUN: 18,
                                  UnitType.FIGHTER: 0, UnitType.INFANTRY: 0,
                                  UnitType.PDS: 0})

    def testOnSampleMap(self):
        """From Thibah (21), next to the gravity rift at 41."""
        b = board_lib.Board.FromMapString(board_lib.SAMPLE_MAP)
        reach = movement.ReachableForUnit(b, b.Find('21'), Unit(UnitType.CARRIER), 'red')
        labels = {b.SystemAt(c).tile_id: p.rifts_exited for c, p in reach.items()}
        # Five neighbours (the sixth, 43, is a supernova), plus 22, 30 and 31
        # by moving out of the rift, each needing one roll.
        self.assertEqual(labels, {'18': 0, '20': 0, '28': 0, '29': 0, '41': 0,
                                  '22': 1, '30': 1, '31': 1})


class TestGravityRiftRoll(unittest.TestCase):
    def testDestroyedOnOneToThree(self):
        self.assertFalse(movement.SurvivesGravityRift(ScriptedDice([3])))
        self.assertTrue(movement.SurvivesGravityRift(ScriptedDice([4])))


if __name__ == '__main__':
    unittest.main()
