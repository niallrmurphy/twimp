#!/usr/bin/env python3

import unittest

from twimp import agents
from twimp import game
from twimp import limits
from twimp.units import Unit, UnitType


class TestLimits(unittest.TestCase):
    def setUp(self):
        self.state = game.NewGame(['sol', 'letnev'], seed=1)
        self.coord = self.state.HomeSystem('sol')
        self.system = self.state.board.SystemAt(self.coord)
        # Sol starts with 2 carriers (capacity 8), 1 destroyer, 3 fighters,
        # and a space dock on Jord.

    def Add(self, *types):
        for t in types:
            self.system.AddUnit('sol', Unit(t))

    def testCapacity(self):
        self.assertEqual(limits.Capacity(self.system, 'sol'), 8)
        self.assertEqual(limits.CapacityExcess(self.system, 'sol'), 0)

    def testSpaceDockCoversThreeFighters(self):
        # 8 capacity + 3 free fighters from the dock = 11 fighters.
        self.Add(*[UnitType.FIGHTER] * 8)
        self.assertEqual(limits.CapacityExcess(self.system, 'sol'), 0)
        self.Add(UnitType.FIGHTER)
        self.assertEqual(limits.CapacityExcess(self.system, 'sol'), 1)

    def testDockDoesntCoverGroundForces(self):
        self.Add(*[UnitType.INFANTRY] * 6)   # 3 fighters (free) + 6 infantry
        self.assertEqual(limits.CapacityExcess(self.system, 'sol'), 0)
        self.Add(*[UnitType.INFANTRY] * 3)
        self.assertEqual(limits.CapacityExcess(self.system, 'sol'), 1)

    def testNoDockNoFreeFighters(self):
        other = self.state.board.SystemAt(self.state.HomeSystem('letnev'))
        other.space['sol'] = [Unit(UnitType.CARRIER)] + [
            Unit(UnitType.FIGHTER) for _ in range(5)]
        self.assertEqual(limits.CapacityExcess(other, 'sol'), 1)

    def testEnforceCapacityDestroysFightersFirst(self):
        self.Add(*[UnitType.FIGHTER] * 8 + [UnitType.INFANTRY])
        removed = limits.EnforceCapacity(self.state, self.coord, 'sol')
        self.assertEqual([u.unit_type for u in removed], [UnitType.FIGHTER])
        self.assertEqual(limits.CapacityExcess(self.system, 'sol'), 0)
        [event] = self.state.log.OfKind('capacity_exceeded')
        self.assertEqual(event.details['units'], ['FIGHTER'])

    def testCarrierLostLeavesFightersStranded(self):
        """After combat, losing a carrier can push fighters over capacity."""
        self.Add(*[UnitType.FIGHTER] * 5)  # 8 fighters: 3 free + 5 carried
        self.system.space['sol'].remove(self.system.ShipsOf('sol')[0])  # a carrier
        self.assertEqual(limits.CapacityExcess(self.system, 'sol'), 1)
        self.assertEqual(len(limits.EnforceCapacity(self.state, self.coord, 'sol')), 1)

    def testFleetPool(self):
        self.assertEqual(limits.FleetPoolExcess(self.system, 'sol', 3), 0)
        self.Add(UnitType.CRUISER, UnitType.DREADNOUGHT)
        self.assertEqual(limits.FleetPoolExcess(self.system, 'sol', 3), 2)
        removed = limits.EnforceFleetPool(self.state, self.coord, 'sol')
        # The cheapest ships go: the destroyer (1) and the cruiser (2).
        self.assertEqual(sorted(u.unit_type.name for u in removed), ['CRUISER', 'DESTROYER'])
        self.assertEqual(len(self.state.log.OfKind('fleet_pool_exceeded')), 1)

    def testFightersDontCountAgainstFleetPool(self):
        self.Add(*[UnitType.FIGHTER] * 4)
        self.assertEqual(limits.FleetPoolExcess(self.system, 'sol', 3), 0)

    def testNothingToEnforce(self):
        self.assertEqual(limits.EnforceCapacity(self.state, self.coord, 'sol'), [])
        self.assertEqual(limits.EnforceFleetPool(self.state, self.coord, 'sol'), [])
        self.assertEqual(len(self.state.log), 1)   # just game_created

    def testBadRemovalChoiceRejected(self):
        class RemoveWrong(agents.GreedyAgent):
            def ChooseUnitsToRemove(self, units, count):
                return [Unit(UnitType.FIGHTER)] * count
        self.Add(*[UnitType.FIGHTER] * 9)
        with self.assertRaises(ValueError):
            limits.EnforceCapacity(self.state, self.coord, 'sol', RemoveWrong())


if __name__ == '__main__':
    unittest.main()
