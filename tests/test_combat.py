#!/usr/bin/env python3

import unittest

from twimp import agents
from twimp import combat
from twimp.units import Unit, UnitType
from tests.fakes import ScriptedDice


def Units(*types):
    return [Unit(t) for t in types]


class RetreatingAgent(agents.GreedyAgent):
    def DeclareRetreat(self, own_units, enemy_units, round_number):
        return True


class WrongTargetAgent(agents.GreedyAgent):
    """Tries to assign hits to a ship that isn't in the combat."""
    def AssignHits(self, units, hits):
        return [Unit(UnitType.CRUISER)] * hits


class TooFewHitsAgent(agents.GreedyAgent):
    def AssignHits(self, units, hits):
        return []


class RecordingAgent(agents.GreedyAgent):
    def __init__(self):
        self.asked = []

    def AssignHits(self, units, hits):
        self.asked.append(hits)
        return super(RecordingAgent, self).AssignHits(units, hits)


class TestSpaceCombat(unittest.TestCase):
    """Dice are rolled in a fixed order: anti-fighter barrage (attacker's
    units, then defender's), then each round's combat rolls (attacker's
    units in order, then defender's)."""

    def assertDiceUsedUp(self, dice):
        self.assertEqual(dice.rolls, [], "unused scripted rolls")

    def testDreadnoughtsVsDestroyers(self):
        """Worked by hand from the rules, one die at a time."""
        dice = ScriptedDice([
            5, 4, 9, 1, 1, 9,   # R1: dreads hit once; destroyers hit twice
            5, 5, 10, 1, 1,     # R2: dreads hit twice; destroyers hit once
            7, 1,               # R3: last dread hits; last destroyer misses
        ])
        result = combat.SpaceCombat(
            Units(UnitType.DREADNOUGHT, UnitType.DREADNOUGHT),
            Units(*[UnitType.DESTROYER] * 4), dice=dice).Resolve()
        self.assertDiceUsedUp(dice)
        self.assertEqual(result.winner, combat.ATTACKER)
        self.assertEqual(len(result.rounds), 3)
        r1, r2, r3 = result.rounds
        # Round 1: both dreadnoughts sustain damage; one destroyer lost.
        self.assertEqual((r1.attacker_hits, r1.defender_hits), (1, 2))
        self.assertEqual(r1.attacker_losses, [])
        self.assertEqual(len(r1.defender_losses), 1)
        # Round 2: a damaged dreadnought takes the hit and is destroyed.
        self.assertEqual(len(r2.attacker_losses), 1)
        self.assertEqual(len(r2.defender_losses), 2)
        self.assertEqual(len(r3.defender_losses), 1)
        self.assertEqual(len(result.attacker_units), 1)
        self.assertTrue(result.attacker_units[0].IsDamaged())
        self.assertEqual(result.defender_units, [])

    def testAntiFighterBarrage(self):
        dice = ScriptedDice([
            9, 9,       # AFB: the destroyer's two dice both hit
            1, 9, 2,    # R1: carrier misses, last fighter hits; destroyer misses
        ])
        result = combat.SpaceCombat(
            Units(UnitType.CARRIER, UnitType.FIGHTER, UnitType.FIGHTER,
                  UnitType.FIGHTER),
            Units(UnitType.DESTROYER), dice=dice).Resolve()
        self.assertDiceUsedUp(dice)
        r1 = result.rounds[0]
        self.assertEqual(r1.defender_afb_hits, 2)
        self.assertEqual([u.unit_type for u in r1.attacker_losses],
                         [UnitType.FIGHTER, UnitType.FIGHTER])
        self.assertEqual(result.winner, combat.ATTACKER)
        self.assertEqual(sorted(u.unit_type.name for u in result.attacker_units),
                         ['CARRIER', 'FIGHTER'])

    def testAntiFighterBarrageOnlyInFirstRound(self):
        dice = ScriptedDice([
            1, 1,       # AFB: misses
            1, 1, 1,    # R1: everyone misses
            9, 1, 1,    # R2: carrier hits; no AFB this round
        ])
        result = combat.SpaceCombat(
            Units(UnitType.CARRIER, UnitType.FIGHTER),
            Units(UnitType.DESTROYER), dice=dice).Resolve()
        self.assertDiceUsedUp(dice)
        self.assertEqual(len(result.rounds), 2)
        self.assertEqual(result.winner, combat.ATTACKER)

    def testAntiFighterBarrageCanEndCombat(self):
        """If AFB leaves a side with no ships, the combat is over."""
        dice = ScriptedDice([9, 10])
        result = combat.SpaceCombat(
            Units(UnitType.FIGHTER, UnitType.FIGHTER),
            Units(UnitType.DESTROYER), dice=dice).Resolve()
        self.assertDiceUsedUp(dice)
        self.assertEqual(result.winner, combat.DEFENDER)
        self.assertEqual(result.rounds[0].attacker_hits, 0)

    def testExcessAfbHitsAreWasted(self):
        dice = ScriptedDice([9, 9, 1, 1])
        # The attacker retreats after round 1, so the test only covers AFB.
        result = combat.SpaceCombat(
            Units(UnitType.CRUISER, UnitType.FIGHTER),
            Units(UnitType.DESTROYER), attacker_agent=RetreatingAgent(),
            dice=dice).Resolve()
        self.assertDiceUsedUp(dice)
        self.assertEqual([u.unit_type for u in result.attacker_units],
                         [UnitType.CRUISER])

    def testDraw(self):
        dice = ScriptedDice([7, 7])
        result = combat.SpaceCombat(Units(UnitType.CRUISER),
                                    Units(UnitType.CRUISER), dice=dice).Resolve()
        self.assertIsNone(result.winner)

    def testHitsCappedAtDamageCapacity(self):
        recorder = RecordingAgent()
        dice = ScriptedDice([1, 7, 7, 7])
        combat.SpaceCombat(Units(UnitType.CRUISER),
                           Units(*[UnitType.CRUISER] * 3),
                           attacker_agent=recorder, dice=dice).Resolve()
        self.assertEqual(recorder.asked, [1])

    def testDefenderRetreat(self):
        """The retreating side still fights the round, then leaves."""
        dice = ScriptedDice([7, 1, 1])
        result = combat.SpaceCombat(
            Units(UnitType.CRUISER), Units(UnitType.CRUISER, UnitType.CRUISER),
            defender_agent=RetreatingAgent(), dice=dice).Resolve()
        self.assertDiceUsedUp(dice)
        self.assertEqual(result.retreated, combat.DEFENDER)
        self.assertEqual(result.winner, combat.ATTACKER)
        self.assertEqual(len(result.defender_units), 1)
        self.assertEqual(result.rounds[0].retreat, combat.DEFENDER)

    def testAttackerCantRetreatIfDefenderDoes(self):
        dice = ScriptedDice([1, 1])
        result = combat.SpaceCombat(
            Units(UnitType.CRUISER), Units(UnitType.CRUISER),
            attacker_agent=RetreatingAgent(), defender_agent=RetreatingAgent(),
            dice=dice).Resolve()
        self.assertEqual(result.retreated, combat.DEFENDER)

    def testRetreatNotAllowed(self):
        dice = ScriptedDice([1, 1, 7, 1])
        result = combat.SpaceCombat(
            Units(UnitType.CRUISER), Units(UnitType.CRUISER),
            defender_agent=RetreatingAgent(), defender_can_retreat=False,
            dice=dice).Resolve()
        self.assertIsNone(result.retreated)
        self.assertEqual(result.winner, combat.ATTACKER)

    def testNoRetreatWhenEnemyDestroyed(self):
        dice = ScriptedDice([7, 1])
        result = combat.SpaceCombat(
            Units(UnitType.CRUISER), Units(UnitType.CRUISER),
            attacker_agent=RetreatingAgent(), dice=dice).Resolve()
        self.assertIsNone(result.retreated)
        self.assertEqual(result.winner, combat.ATTACKER)

    def testNoCombatWithoutShips(self):
        result = combat.SpaceCombat(Units(UnitType.CRUISER), [],
                                    dice=ScriptedDice([])).Resolve()
        self.assertEqual(result.winner, combat.ATTACKER)
        self.assertEqual(result.rounds, [])

    def testOnlyShipsAllowed(self):
        with self.assertRaises(ValueError):
            combat.SpaceCombat(Units(UnitType.CRUISER), Units(UnitType.PDS))

    def testIllegalAssignmentsRejected(self):
        for agent in (WrongTargetAgent(), TooFewHitsAgent()):
            c = combat.SpaceCombat(Units(UnitType.CRUISER), Units(UnitType.CRUISER),
                                   defender_agent=agent, dice=ScriptedDice([7, 1]))
            with self.assertRaises(combat.IllegalAssignment):
                c.Resolve()

    def testCantOverAssignToOneShip(self):
        cruiser = Unit(UnitType.CRUISER)
        with self.assertRaises(combat.IllegalAssignment):
            combat.ApplyAssignment([cruiser, Unit(UnitType.CRUISER)],
                                   [cruiser, cruiser], 2)


class TestGroundCombat(unittest.TestCase):
    def testInfantryHitOnEight(self):
        dice = ScriptedDice([8, 7, 1])
        result = combat.GroundCombat(Units(UnitType.INFANTRY, UnitType.INFANTRY),
                                     Units(UnitType.INFANTRY), dice=dice).Resolve()
        self.assertEqual(dice.rolls, [])
        self.assertEqual(result.winner, combat.ATTACKER)
        self.assertEqual(len(result.attacker_units), 2)

    def testFightsUntilOneSideIsGone(self):
        dice = ScriptedDice([1, 1, 1, 9, 1, 1, 1, 10])
        result = combat.GroundCombat(Units(UnitType.INFANTRY),
                                     Units(UnitType.INFANTRY, UnitType.INFANTRY),
                                     dice=dice).Resolve()
        self.assertEqual(result.winner, combat.DEFENDER)
        self.assertEqual(len(result.rounds), 3)
        self.assertEqual(len(result.defender_units), 1)

    def testDoesNotChangeCallersList(self):
        attackers = Units(UnitType.INFANTRY)
        combat.GroundCombat(attackers, Units(UnitType.INFANTRY),
                            dice=ScriptedDice([1, 8])).Resolve()
        self.assertEqual(len(attackers), 1)

    def testOnlyGroundForcesAllowed(self):
        for units in (Units(UnitType.FIGHTER), Units(UnitType.PDS)):
            with self.assertRaises(ValueError):
                combat.GroundCombat(Units(UnitType.INFANTRY), units)


if __name__ == '__main__':
    unittest.main()
