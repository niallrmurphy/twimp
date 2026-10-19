#!/usr/bin/env python3

import unittest

from twimp import agents
from twimp import board
from twimp import invasion
from twimp.units import Unit, UnitType
from tests.fakes import ScriptedDice

RED, BLUE = 'red', 'blue'


def Units(*types):
    return [Unit(t) for t in types]


def Infantry(n):
    return Units(*[UnitType.INFANTRY] * n)


def HeldPlanet(controller, *types, name='Arinam', resources=1, influence=2):
    planet = board.Planet(name, resources, influence)
    planet.controller = controller
    for unit in Units(*types):
        planet.AddUnit(controller, unit)
    return planet


class TestInvasion(unittest.TestCase):
    """Dice are rolled in step order: bombardment (in the order of the
    agent's choices), space cannon defense (planet by planet), then ground
    combat (planet by planet; attacker's units, then defender's, each round)."""

    def assertDiceUsedUp(self, dice):
        self.assertEqual(dice.rolls, [], "unused scripted rolls")

    def Invade(self, planets, ships=(), ground_forces=(), rolls=(), agents_map=None):
        dice = ScriptedDice(rolls)
        result = invasion.Invasion(RED, list(ships), list(ground_forces), planets,
                                   agents=agents_map, dice=dice).Resolve()
        self.assertDiceUsedUp(dice)
        return result

    def testLandOnNeutralPlanet(self):
        planet = board.Planet('Lodor', 3, 1)
        result = self.Invade([planet], ground_forces=Infantry(2))
        self.assertEqual(planet.controller, RED)
        self.assertTrue(planet.exhausted)
        self.assertEqual(len(planet.GroundForces(RED)), 2)
        self.assertTrue(result.ReportFor(planet).gained_control)
        self.assertEqual(result.ground_forces_in_space, [])

    def testBombardThenGroundCombat(self):
        planet = HeldPlanet(BLUE, UnitType.INFANTRY, UnitType.INFANTRY)
        result = self.Invade(
            [planet], ships=Units(UnitType.DREADNOUGHT),
            ground_forces=Infantry(3),
            rolls=[5,          # bombardment: hit, 1 blue infantry lost
                   8, 1, 1,    # ground combat R1: red hits once
                   1])         # blue's last infantry misses
        report = result.ReportFor(planet)
        self.assertEqual(report.bombardment_hits, 1)
        self.assertEqual(len(report.bombardment_losses), 1)
        self.assertEqual(len(report.ground_combat.rounds), 1)
        self.assertEqual(planet.GroundForces(BLUE), [])
        self.assertEqual(len(planet.GroundForces(RED)), 3)
        self.assertEqual(planet.controller, RED)
        self.assertTrue(planet.exhausted)

    def testPlanetaryShieldBlocksBombardment(self):
        planet = HeldPlanet(BLUE, UnitType.INFANTRY, UnitType.PDS)
        inv = invasion.Invasion(RED, Units(UnitType.DREADNOUGHT), [], [planet])
        self.assertTrue(inv.IsShielded(planet))
        self.assertEqual(inv.BombardablePlanets(), [])

    def testSpaceCannonDefenseThenCapture(self):
        planet = HeldPlanet(BLUE, UnitType.INFANTRY, UnitType.PDS)
        result = self.Invade(
            [planet], ships=Units(UnitType.DREADNOUGHT),
            ground_forces=Infantry(2),
            rolls=[6,      # space cannon defense: PDS hits a landing infantry
                   8,      # ground combat: red's survivor hits
                   1])     # blue misses
        report = result.ReportFor(planet)
        self.assertEqual(report.bombardment_hits, 0)
        self.assertEqual(report.space_cannon_hits, 1)
        self.assertEqual(len(report.space_cannon_losses), 1)
        self.assertEqual(planet.controller, RED)
        # The captured PDS is destroyed.
        self.assertEqual([u.unit_type for u in report.structures_destroyed],
                         [UnitType.PDS])
        self.assertEqual(planet.UnitsOf(BLUE), [])

    def testWarSunIgnoresPlanetaryShield(self):
        planet = HeldPlanet(BLUE, UnitType.INFANTRY, UnitType.PDS)
        result = self.Invade(
            [planet], ships=Units(UnitType.WARSUN), ground_forces=Infantry(2),
            rolls=[3, 3, 1,   # bombardment 3x3: two hits, only one infantry to lose
                   1])        # space cannon defense misses
        report = result.ReportFor(planet)
        self.assertEqual(report.bombardment_hits, 2)
        self.assertEqual(len(report.bombardment_losses), 1)
        self.assertIsNone(report.ground_combat)
        self.assertEqual(planet.controller, RED)

    def testDefenderHolds(self):
        planet = HeldPlanet(BLUE, UnitType.INFANTRY, UnitType.INFANTRY)
        result = self.Invade([planet], ground_forces=Infantry(1),
                             rolls=[1, 8, 1])
        self.assertEqual(result.ReportFor(planet).ground_combat.winner, 'defender')
        self.assertEqual(planet.controller, BLUE)
        self.assertFalse(result.ReportFor(planet).gained_control)
        self.assertEqual(planet.GroundForces(RED), [])

    def testMutualDestructionLeavesControl(self):
        planet = HeldPlanet(BLUE, UnitType.INFANTRY)
        planet.exhausted = False
        self.Invade([planet], ground_forces=Infantry(1), rolls=[8, 8])
        self.assertEqual(planet.controller, BLUE)
        self.assertFalse(planet.exhausted)
        self.assertTrue(planet.IsEmpty())

    def testUndefendedStructuresAreDestroyed(self):
        planet = HeldPlanet(BLUE, UnitType.SPACEDOCK)
        result = self.Invade([planet], ground_forces=Infantry(1))
        self.assertEqual(planet.controller, RED)
        self.assertEqual(len(result.ReportFor(planet).structures_destroyed), 1)

    def testReinforcingOwnPlanet(self):
        planet = HeldPlanet(RED, UnitType.INFANTRY)
        planet.exhausted = False

        class Reinforce(agents.GreedyAgent):
            def CommitGroundForces(self, player, ground_forces, planets):
                return {planets[0]: ground_forces}

        result = self.Invade([planet], ground_forces=Infantry(1),
                             agents_map={RED: Reinforce()})
        self.assertFalse(result.ReportFor(planet).gained_control)
        self.assertFalse(planet.exhausted)
        self.assertEqual(len(planet.GroundForces(RED)), 2)

    def testUncommittedForcesStayInSpace(self):
        planet = board.Planet('Lodor', 3, 1)

        class LandOne(agents.GreedyAgent):
            def CommitGroundForces(self, player, ground_forces, planets):
                return {planets[0]: ground_forces[:1]}

        result = self.Invade([planet], ground_forces=Infantry(2),
                             agents_map={RED: LandOne()})
        self.assertEqual(len(result.ground_forces_in_space), 1)
        self.assertEqual(len(planet.GroundForces(RED)), 1)

    def testSplitInvasionAcrossPlanets(self):
        weak = HeldPlanet(BLUE, UnitType.INFANTRY, name='Weak')
        empty = board.Planet('Empty', 0, 1)
        forces = Infantry(3)

        class Split(agents.GreedyAgent):
            def CommitGroundForces(self, player, ground_forces, planets):
                return {weak: ground_forces[:2], empty: ground_forces[2:]}

        self.Invade([weak, empty], ground_forces=forces,
                    agents_map={RED: Split()}, rolls=[8, 1, 1])
        self.assertEqual(weak.controller, RED)
        self.assertEqual(empty.controller, RED)

    def testIllegalBombardmentTarget(self):
        planet = HeldPlanet(BLUE, UnitType.INFANTRY, UnitType.PDS)

        class BombardAnyway(agents.GreedyAgent):
            def ChooseBombardment(self, player, units, planets):
                return [(units[0], planet)]

        # The shielded planet isn't offered, so nothing is bombardable and
        # the agent isn't even asked. Add an unshielded one to get it asked.
        other = HeldPlanet(BLUE, UnitType.INFANTRY, name='Other')
        inv = invasion.Invasion(RED, Units(UnitType.DREADNOUGHT), [],
                                [planet, other], agents={RED: BombardAnyway()},
                                dice=ScriptedDice([5]))
        with self.assertRaises(invasion.IllegalChoice):
            inv.Resolve()

    def testBombardingTwiceIsIllegal(self):
        planet = HeldPlanet(BLUE, UnitType.INFANTRY)

        class Twice(agents.GreedyAgent):
            def ChooseBombardment(self, player, units, planets):
                return [(units[0], planets[0])] * 2

        inv = invasion.Invasion(RED, Units(UnitType.DREADNOUGHT), [], [planet],
                                agents={RED: Twice()}, dice=ScriptedDice([1, 1]))
        with self.assertRaises(invasion.IllegalChoice):
            inv.Resolve()

    def testIllegalCommits(self):
        planet = board.Planet('Lodor', 3, 1)
        stranger = Unit(UnitType.INFANTRY)

        class Smuggle(agents.GreedyAgent):
            def CommitGroundForces(self, player, ground_forces, planets):
                return {planets[0]: [stranger]}

        class Elsewhere(agents.GreedyAgent):
            def CommitGroundForces(self, player, ground_forces, planets):
                return {board.Planet('Faraway', 1, 1): ground_forces}

        for agent in (Smuggle(), Elsewhere()):
            inv = invasion.Invasion(RED, [], Infantry(1), [planet],
                                    agents={RED: agent}, dice=ScriptedDice([]))
            with self.assertRaises(invasion.IllegalChoice):
                inv.Resolve()

    def testOnlyGroundForcesCanInvade(self):
        with self.assertRaises(ValueError):
            invasion.Invasion(RED, [], Units(UnitType.FIGHTER), [])


if __name__ == '__main__':
    unittest.main()
