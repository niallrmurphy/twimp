#!/usr/bin/env python3

import json
import unittest

from twimp import agents
from twimp import decisions
from twimp import dice as dice_lib
from twimp import game
from twimp import rounds
from twimp import tactical
from twimp.units import Unit, UnitType
from tests.test_tactical import LODOR, MAP, SOL_HOME


class Recorder(decisions.DecisionAgent):
    """Answers with scripted JSON answers (or the default), recording decisions."""
    def __init__(self, name, answers=None):
        super(Recorder, self).__init__(name)
        self.answers = dict(answers or {})
        self.asked = []

    def Ask(self, decision):
        json.dumps(decision.ToJson())   # must always be serialisable
        self.asked.append(decision)
        answer = self.answers.pop(decision.kind, decision.default)
        return decision.parse(answer)


class TestDefaultsMatchGreedy(unittest.TestCase):
    def testWholeGamesMatch(self):
        factions = ['sol', 'letnev', 'jolnar', 'sardakk', 'xxcha', 'yssaril']
        for seed in range(4):
            results = []
            for make in (lambda n: agents.GreedyAgent(), decisions.DefaultingAgent):
                state = game.NewGame(factions, seed=seed)
                players = {p.name: make(p.name) for p in state.players}
                dice = dice_lib.Dice(seed=seed)
                for _ in range(3):
                    rounds.PlayRound(state, players, dice)
                results.append(game.ToDict(state))
            self.assertEqual(results[0], results[1], seed)


class TestParsing(unittest.TestCase):
    """Each decision's parse accepts its default and rejects bad answers."""

    def setUp(self):
        self.state = game.NewGame(['sol', 'letnev'], MAP, speaker='sol')
        self.agent = Recorder('sol')

    def Decide(self, method, *args):
        """Call an agent method, then return its decision for direct parsing."""
        getattr(self.agent, method)(*args)
        return self.agent.asked[-1]

    def assertRejects(self, decision, *answers):
        for answer in answers:
            with self.assertRaises(ValueError, msg=repr(answer)):
                decision.parse(answer)

    def testAction(self):
        d = self.Decide('ChooseAction', self.state, 'sol', ['tactical', 'pass'])
        self.assertEqual(d.parse('pass'), 'pass')
        self.assertRejects(d, 'strategic', None)

    def testActivation(self):
        options = tactical.ActivationOptions(self.state, 'sol')
        d = self.Decide('ChooseActivation', self.state, 'sol', options)
        self.assertEqual(d.parse(d.default), LODOR)
        self.assertEqual(d.parse('0,-1'), SOL_HOME)
        self.assertRejects(d, '9,9', 7)

    def testMovement(self):
        self.state.board.SystemAt(LODOR).command_tokens.add('sol')
        options = tactical.MoveOptions(self.state, 'sol', LODOR)
        transportable = {o.start: tactical.Transportable(self.state, 'sol', o.start)
                         for o in options}
        d = self.Decide('ChooseMovement', self.state, 'sol', LODOR, options, transportable)
        carrier = next(i for i, o in enumerate(options) if o.ship.unit_type == UnitType.CARRIER)
        moves = d.parse([{'ship': carrier, 'ground': 3, 'fighters': 1}])
        self.assertEqual(len(moves[0][1]), 4)
        # Spares are taken before the last infantry guarding Jord.
        jord = self.state.board.SystemAt(SOL_HOME).planets[0]
        self.assertIs(moves[0][1][0], jord.GroundForces('sol')[1])
        self.assertRejects(
            d, [{'ship': carrier, 'ground': 5}],              # over capacity
            [{'ship': carrier}, {'ship': carrier}],            # same ship twice
            [{'ship': 99}], [{'ground': 1}], 'all',
            [{'ship': carrier, 'ground': -1}])
        # Two carriers can't share more infantry than there is.
        other = next(i for i, o in enumerate(options)
                     if o.ship.unit_type == UnitType.CARRIER and i != carrier)
        self.assertRejects(d, [{'ship': carrier, 'ground': 4},
                               {'ship': other, 'ground': 2}])

    def testHits(self):
        dread, cruiser = Unit(UnitType.DREADNOUGHT), Unit(UnitType.CRUISER)
        d = self.Decide('AssignHits', [dread, cruiser], 2)
        self.assertEqual(d.parse([0, 0]), [dread, dread])
        self.assertEqual(d.parse(d.default), [dread, cruiser])
        self.assertRejects(d, [1, 1], [0], [0, 5], 'both')

    def testYesNo(self):
        d = self.Decide('DeclareRetreat', [], [], 1)
        self.assertTrue(d.parse(True))
        self.assertRejects(d, 'yes', 1)
        d = self.Decide('ChooseRemoveCustodians', self.state, 'sol', 6)
        self.assertTrue(d.default)

    def testLanding(self):
        planets = self.state.board.SystemAt(LODOR).planets + \
            self.state.board.SystemAt(SOL_HOME).planets
        forces = [Unit(UnitType.INFANTRY) for _ in range(3)]
        d = self.Decide('CommitGroundForces', 'sol', forces, planets)
        choice = d.parse([2, 0])
        self.assertEqual(choice, {planets[0]: forces[:2]})
        self.assertRejects(d, [2, 2], [1], [-1, 0], 'all')

    def testBombardment(self):
        planets = self.state.board.SystemAt(SOL_HOME).planets
        dread = Unit(UnitType.DREADNOUGHT)
        d = self.Decide('ChooseBombardment', 'letnev', [dread], planets)
        self.assertEqual(d.parse(0), [(dread, planets[0])])
        self.assertEqual(d.parse(None), [])
        self.assertRejects(d, 3, 'Jord')

    def testRemove(self):
        units = [Unit(UnitType.FIGHTER), Unit(UnitType.INFANTRY)]
        d = self.Decide('ChooseUnitsToRemove', units, 1)
        self.assertEqual(d.parse([1]), [units[1]])
        self.assertRejects(d, [0, 1], [0, 0], [])

    def testProduction(self):
        context = tactical.ProductionContext(
            limit=4, budget=3, can_produce_ships=True, fleet_room=1, fighter_room=0,
            plastic_room={UnitType.CRUISER: 8, UnitType.INFANTRY: None,
                          UnitType.FIGHTER: None})
        d = self.Decide('ChooseProduction', self.state, 'sol', SOL_HOME, context)
        self.assertEqual(d.parse({'cruiser': 1, 'infantry': 2}),
                         {UnitType.CRUISER: 1, UnitType.INFANTRY: 2})
        self.assertEqual(d.parse({'infantry': 0}), {})
        self.assertRejects(d, {'cruiser': 2}, {'infantry': 5}, {'warsun': 1},
                           {'fighter': 1}, {'infantry': -1}, ['cruiser'])

    def testCommandTokens(self):
        d = self.Decide('ChooseCommandTokens', self.state, 'sol', 10)
        self.assertEqual(sum(d.default), 10)
        self.assertEqual(d.parse([5, 3, 2]), (5, 3, 2))
        self.assertRejects(d, [5, 5, 5], [10, 0], [11, -1, 0], 'even')

    def testRetreatSystem(self):
        d = self.Decide('ChooseRetreatSystem', self.state, 'sol', [SOL_HOME, LODOR])
        self.assertEqual(d.parse('1,-1'), LODOR)
        self.assertRejects(d, '0,0')


class TestScriptedWebLikeTurn(unittest.TestCase):
    def testTurnFromJsonAnswers(self):
        state = game.NewGame(['sol', 'letnev'], MAP, speaker='sol')
        sol = Recorder('sol', {'activation': '1,-1', 'landing': [1]})
        tactical.TakeTacticalAction(state, 'sol', {'sol': sol}, dice_lib.Dice(seed=1))
        lodor = state.board.SystemAt(LODOR).planets[0]
        self.assertEqual(lodor.controller, 'sol')
        self.assertEqual(len(lodor.GroundForces('sol')), 1)
        self.assertEqual([d.kind for d in sol.asked], ['activation', 'movement', 'landing'])


if __name__ == '__main__':
    unittest.main()
