#!/usr/bin/env python3

import unittest

from twimp import cli_agent
from twimp import game
from twimp import play_turn
from twimp import tactical
from twimp.units import Unit, UnitType


def Agent(*answers):
    """A CliAgent fed the given answers; anything printed is collected."""
    answers = list(answers)
    printed = []

    def Input(prompt):
        printed.append(prompt)
        if not answers:
            raise EOFError
        return answers.pop(0)

    agent = cli_agent.CliAgent('sol', Input, printed.append)
    agent.printed = printed
    agent.unused = answers
    return agent


def Context(**overrides):
    values = dict(limit=6, budget=4, can_produce_ships=True, fleet_room=1, fighter_room=2,
                  plastic_room={UnitType.CRUISER: 8, UnitType.INFANTRY: None,
                                UnitType.FIGHTER: None, UnitType.CARRIER: 4})
    values.update(overrides)
    return tactical.ProductionContext(**values)


class TestCliAgent(unittest.TestCase):
    def testAssignHits(self):
        dread, cruiser = Unit(UnitType.DREADNOUGHT), Unit(UnitType.CRUISER)
        agent = Agent('2 2', '1', '1 1')   # cruiser can't take 2; wrong count; ok
        self.assertEqual(agent.AssignHits([dread, cruiser], 2), [dread, dread])
        self.assertEqual(agent.unused, [])
        self.assertTrue(any('can only take 1' in str(p) for p in agent.printed))

    def testBlankAcceptsSuggestion(self):
        dread, cruiser = Unit(UnitType.DREADNOUGHT), Unit(UnitType.CRUISER)
        # Greedy would use the dreadnought's Sustain Damage first.
        self.assertEqual(Agent('').AssignHits([dread, cruiser], 1), [dread])
        # End of input also accepts the suggestion.
        self.assertEqual(Agent().AssignHits([dread, cruiser], 1), [dread])

    def testRetreat(self):
        self.assertTrue(Agent('maybe', 'y').DeclareRetreat([], [], 1))
        self.assertFalse(Agent('').DeclareRetreat([], [], 1))

    def testProduction(self):
        agent = Agent('warsun', 'cruiser=2', 'infantry=9', 'cruiser=1, infantry=2')
        state = game.NewGame(['sol', 'letnev'], seed=1)
        self.assertEqual(agent.ChooseProduction(state, 'sol', state.HomeSystem('sol'),
                                                Context()),
                         {UnitType.CRUISER: 1, UnitType.INFANTRY: 2})
        self.assertEqual(agent.unused, [])
        complaints = ' '.join(str(p) for p in agent.printed)
        self.assertIn('Unknown unit', complaints)
        self.assertIn('fleet pool', complaints)
        self.assertIn('limit is 6', complaints)

    def testProductionProblems(self):
        problem = cli_agent._ProductionProblem
        self.assertIsNone(problem({UnitType.CARRIER: 1, UnitType.FIGHTER: 1},
                                  Context()))
        self.assertIn('costs', problem({UnitType.CARRIER: 1, UnitType.CRUISER: 1},
                                       Context(fleet_room=2)))
        self.assertIn('blockaded', problem({UnitType.FIGHTER: 2},
                                           Context(can_produce_ships=False)))
        # A new carrier makes room for more fighters.
        self.assertIn('room for 2', problem({UnitType.FIGHTER: 3}, Context()))
        self.assertIsNone(problem({UnitType.CARRIER: 1, UnitType.FIGHTER: 2},
                                  Context(budget=6)))


class TestPlayTurn(unittest.TestCase):
    def Play(self, answers, *argv):
        answers = list(answers)
        out = []

        def Input(prompt):
            out.append(prompt)
            if not answers:
                raise EOFError
            return answers.pop(0)

        play_turn.main(list(argv), input_fn=Input, print_fn=out.append)
        return '\n'.join(str(o) for o in out), answers

    def testHumanTurn(self):
        text, unused = self.Play(
            ['33',      # activate Corneeq/Resculon
             '1',       # move just the first carrier...
             '2 0',     # ...carrying 2 infantry, no fighters
             '1', '1'], # land 1 on Corneeq and 1 on Resculon
            '--human', 'sol', '--seed', '2', '--quiet')
        self.assertEqual(unused, [])
        self.assertIn('sol activates 33 (Corneeq, Resculon).', text)
        self.assertIn('moves carrier from 1H (1H > 33) carrying 2 infantry', text)
        self.assertIn('Corneeq: lands 1 infantry, takes control', text)
        self.assertIn('Resculon: lands 1 infantry, takes control', text)

    def testComputerTurns(self):
        text, _ = self.Play([], '--actions', '6', '--seed', '2', '--agent', 'random')
        self.assertEqual(text.count(' activates '), 6)
        self.assertIn('Round 1, strategy phase', text)

    def testRunsOutOfTacticTokens(self):
        text, _ = self.Play([], '--factions', 'sol,letnev', '--actions', '9', '--quiet')
        self.assertEqual(text.count(' activates '), 6)
        self.assertIn('Nobody has tactic tokens left.', text)


if __name__ == '__main__':
    unittest.main()
