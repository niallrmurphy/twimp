#!/usr/bin/env python3

import collections
import unittest

from twimp import agents
from twimp.units import Unit, UnitType


def Units(*types):
    return [Unit(t) for t in types]


def Counts(assignment):
    return collections.Counter(u.unit_type for u in assignment)


class TestGreedyAgent(unittest.TestCase):
    def setUp(self):
        self.agent = agents.GreedyAgent()

    def testFightersFirst(self):
        units = Units(UnitType.CRUISER, UnitType.FIGHTER, UnitType.FIGHTER)
        self.assertEqual(Counts(self.agent.AssignHits(units, 2)),
                         {UnitType.FIGHTER: 2})

    def testSustainBeforeLosses(self):
        units = Units(UnitType.DESTROYER, UnitType.DREADNOUGHT, UnitType.WARSUN)
        assignment = self.agent.AssignHits(units, 3)
        self.assertEqual(Counts(assignment), {UnitType.DREADNOUGHT: 1,
                                              UnitType.WARSUN: 1,
                                              UnitType.DESTROYER: 1})

    def testCarriersBeforeDamagedDreadnoughts(self):
        units = Units(UnitType.DREADNOUGHT, UnitType.CARRIER)
        self.assertEqual(Counts(self.agent.AssignHits(units, 2)),
                         {UnitType.DREADNOUGHT: 1, UnitType.CARRIER: 1})

    def testSecondHitDestroysDreadnought(self):
        units = Units(UnitType.DREADNOUGHT)
        assignment = self.agent.AssignHits(units, 2)
        self.assertEqual(assignment, [units[0], units[0]])

    def testAlreadyDamagedShipsCanOnlyTakeOne(self):
        units = Units(UnitType.DREADNOUGHT, UnitType.CRUISER)
        units[0].ReceiveHits(1)
        self.assertEqual(Counts(self.agent.AssignHits(units, 2)),
                         {UnitType.DREADNOUGHT: 1, UnitType.CRUISER: 1})

    def testAssignsEverythingOnWipeout(self):
        units = Units(UnitType.WARSUN, UnitType.FLAGSHIP, UnitType.CARRIER,
                      UnitType.FIGHTER)
        self.assertEqual(len(self.agent.AssignHits(units, 6)), 6)

    def testNeverRetreats(self):
        self.assertFalse(self.agent.DeclareRetreat([], [], 1))


if __name__ == '__main__':
    unittest.main()
