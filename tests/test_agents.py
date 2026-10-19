#!/usr/bin/env python3

import collections
import unittest

from twimp import agents
from twimp import board
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

    def testAssignsHitsToInfantry(self):
        units = Units(UnitType.INFANTRY, UnitType.INFANTRY)
        self.assertEqual(len(self.agent.AssignHits(units, 1)), 1)


class TestGreedyInvasionChoices(unittest.TestCase):
    def setUp(self):
        self.agent = agents.GreedyAgent()
        self.ours = board.Planet('Ours', 4, 4)
        self.ours.controller = 'red'
        self.guarded = board.Planet('Guarded', 4, 4)
        self.guarded.controller = 'blue'
        for unit in Units(UnitType.INFANTRY, UnitType.INFANTRY):
            self.guarded.AddUnit('blue', unit)
        self.poor = board.Planet('Poor', 0, 1)
        self.rich = board.Planet('Rich', 3, 1)

    def testOneEachOnUndefendedPlanetsRichestFirst(self):
        forces = Units(UnitType.INFANTRY, UnitType.INFANTRY)
        choice = self.agent.CommitGroundForces(
            'red', forces, [self.ours, self.guarded, self.poor, self.rich])
        self.assertEqual(choice, {self.rich: forces[:1], self.poor: forces[1:]})

    def testRestGoToWeakestDefendedPlanet(self):
        forces = Units(*[UnitType.INFANTRY] * 5)
        choice = self.agent.CommitGroundForces(
            'red', forces, [self.ours, self.guarded, self.rich])
        self.assertEqual(choice, {self.rich: forces[:1], self.guarded: forces[1:]})

    def testSurplusStaysOnBestUndefendedPlanet(self):
        forces = Units(*[UnitType.INFANTRY] * 3)
        choice = self.agent.CommitGroundForces('red', forces, [self.poor, self.rich])
        self.assertEqual(choice, {self.rich: [forces[0], forces[2]],
                                  self.poor: [forces[1]]})

    def testNothingToCommitTo(self):
        self.assertEqual(self.agent.CommitGroundForces(
            'red', Units(UnitType.INFANTRY), [self.ours]), {})

    def testBombardsMostDefendedPlanet(self):
        lightly = board.Planet('Lightly', 1, 1)
        lightly.AddUnit('blue', Units(UnitType.INFANTRY)[0])
        bombarders = Units(UnitType.DREADNOUGHT, UnitType.DREADNOUGHT)
        choice = self.agent.ChooseBombardment('red', bombarders,
                                              [lightly, self.guarded])
        self.assertEqual(choice, [(bombarders[0], self.guarded),
                                  (bombarders[1], self.guarded)])


if __name__ == '__main__':
    unittest.main()
