#!/usr/bin/env python3

import unittest

from twimp import agents
from twimp import game
from twimp import hexes
from twimp import rounds
from twimp import tactical
from twimp.units import Unit, UnitType
from tests.fakes import ScriptedDice
from tests.test_tactical import MAP, MECATOL, SOL_HOME, LODOR, Scripted

INF = UnitType.INFANTRY


class Choosy(Scripted):
    """Scripted, plus fixed action and command token choices."""
    def __init__(self, actions=None, tokens=None, custodians=True, **kwargs):
        super(Choosy, self).__init__(**kwargs)
        self.actions = list(actions or [])
        self.tokens = tokens
        self.custodians = custodians

    def ChooseAction(self, state, player, options):
        if self.actions:
            return self.actions.pop(0)
        return 'pass'

    def ChooseCommandTokens(self, state, player, total):
        if self.tokens is None:
            return super(Choosy, self).ChooseCommandTokens(state, player, total)
        return self.tokens

    def ChooseRemoveCustodians(self, state, player, cost):
        return self.custodians


def NewState(factions=('sol', 'letnev')):
    return game.NewGame(list(factions), MAP, speaker='sol')


class TestActionPhase(unittest.TestCase):
    def testEveryonePasses(self):
        state = NewState()
        seen = []
        rounds.PlayActionPhase(state, {'sol': Choosy(), 'letnev': Choosy()},
                               observer=lambda kind, player, **_: seen.append((kind, player)))
        self.assertEqual(seen, [('pass', 'sol'), ('pass', 'letnev')])
        self.assertEqual(state.passed, {'sol', 'letnev'})
        self.assertEqual(state.phase, game.ACTION)

    def testTurnsAlternateUntilAllPass(self):
        state = NewState()
        seen = []
        sol = Choosy(actions=['tactical', 'tactical', 'pass'], activate=SOL_HOME)
        letnev = Choosy(actions=['tactical', 'pass'], activate=hexes.SOUTH_EAST)
        # Second time round, activate somewhere new (home now has a token).
        sol_targets = [SOL_HOME, LODOR]
        sol.ChooseActivation = lambda state, player, options: sol_targets.pop(0)
        rounds.PlayActionPhase(state, {'sol': sol, 'letnev': letnev},
                               observer=lambda kind, player, **_: seen.append((kind, player)))
        self.assertEqual(seen, [('tactical', 'sol'), ('tactical', 'letnev'),
                                ('tactical', 'sol'), ('pass', 'letnev'),
                                ('pass', 'sol')])

    def testNoTacticTokensMeansPass(self):
        state = NewState()
        state.Player('sol').tactic_tokens = 0
        self.assertEqual(rounds.ActionOptions(state, 'sol'), ['pass'])
        with self.assertRaises(tactical.IllegalAction):
            rounds.PlayActionPhase(state, {'sol': Choosy(actions=['tactical'])})

    def testNextToAct(self):
        state = game.NewGame(['sol', 'letnev', 'jolnar'], speaker='letnev')
        self.assertEqual(state.SeatOrderFromSpeaker(), ['letnev', 'jolnar', 'sol'])
        self.assertEqual(rounds.NextToAct(state), 'letnev')
        state.passed = {'jolnar'}
        self.assertEqual(rounds.NextToAct(state, after='letnev'), 'sol')
        state.passed = {'jolnar', 'sol', 'letnev'}
        self.assertIsNone(rounds.NextToAct(state))


class TestCustodians(unittest.TestCase):
    def setUp(self):
        self.state = NewState()
        # Give Sol enough influence: Lodor (1) isn't enough, so add trade goods.
        self.state.Player('sol').trade_goods = 4

    def Land(self, agent):
        def CarrierWithInfantry(options, transportable):
            carrier = next(o for o in options if o.ship.unit_type == UnitType.CARRIER)
            ground = [u for u in transportable[carrier.start] if u.IsGroundForce()]
            return [(carrier, ground[:2])]
        agent.activate, agent.move = MECATOL, CarrierWithInfantry
        return tactical.TakeTacticalAction(self.state, 'sol', {'sol': agent},
                                           ScriptedDice([]))

    def testRemoveAndLand(self):
        report = self.Land(Choosy())
        self.assertTrue(report.removed_custodians)
        self.assertFalse(self.state.custodians)
        self.assertEqual(self.state.Player('sol').victory_points, 1)
        # Jord's 2 influence plus 4 trade goods.
        self.assertTrue(self.state.board.SystemAt(SOL_HOME).planets[0].exhausted)
        self.assertEqual(self.state.Player('sol').trade_goods, 0)
        self.assertEqual(self.state.board.SystemAt(MECATOL).planets[0].controller, 'sol')
        self.assertIn('custodians token (+1 victory point)',
                      tactical.DescribeReport(self.state, report))

    def testDeclining(self):
        report = self.Land(Choosy(custodians=False))
        self.assertFalse(report.removed_custodians)
        self.assertTrue(self.state.custodians)
        self.assertIsNone(self.state.board.SystemAt(MECATOL).planets[0].controller)

    def testCantAfford(self):
        self.state.Player('sol').trade_goods = 3
        asked = []
        agent = Choosy()
        agent.ChooseRemoveCustodians = lambda *a: asked.append(a) or True
        self.Land(agent)
        self.assertEqual(asked, [])
        self.assertTrue(self.state.custodians)

    def testWinning(self):
        self.state.Player('sol').victory_points = 9
        sol = Choosy(actions=['tactical'])

        def CarrierWithInfantry(options, transportable):
            carrier = next(o for o in options if o.ship.unit_type == UnitType.CARRIER)
            return [(carrier, [u for u in transportable[carrier.start]
                               if u.IsGroundForce()][:1])]
        sol.activate, sol.move = MECATOL, CarrierWithInfantry
        winner = rounds.PlayActionPhase(self.state, {'sol': sol}, ScriptedDice([]))
        self.assertEqual(winner, 'sol')
        self.assertEqual(self.state.Winner(), 'sol')
        self.assertEqual(len(self.state.log.OfKind('game_won')), 1)


class TestStatusPhase(unittest.TestCase):
    def setUp(self):
        self.state = NewState()

    def testCleanUp(self):
        board = self.state.board
        board.SystemAt(LODOR).command_tokens.add('sol')
        board.SystemAt(MECATOL).command_tokens.add('letnev')
        self.state.Player('sol').tactic_tokens = 2
        board.SystemAt(SOL_HOME).planets[0].exhausted = True
        dread = board.SystemAt(hexes.SOUTH_EAST).ShipsOf('letnev')[0]
        dread.damaged = True
        self.state.passed = {'sol', 'letnev'}
        rounds.PlayStatusPhase(self.state)
        self.assertTrue(all(not s.command_tokens for s in board.systems.values()))
        self.assertFalse(board.SystemAt(SOL_HOME).planets[0].exhausted)
        self.assertFalse(dread.damaged)
        self.assertEqual(self.state.passed, set())
        # Sol had 2+3+2 = 7 and gains 2. Sol's home has 3 non-fighter ships,
        # filling the fleet pool, so greedy puts one token there.
        sol = self.state.Player('sol')
        self.assertEqual((sol.tactic_tokens, sol.fleet_tokens, sol.strategy_tokens),
                         (3, 4, 2))

    def testRedistribute(self):
        rounds.PlayStatusPhase(self.state, {'sol': Choosy(tokens=(1, 8, 1))})
        sol = self.state.Player('sol')
        self.assertEqual((sol.tactic_tokens, sol.fleet_tokens, sol.strategy_tokens),
                         (1, 8, 1))

    def testBadSplit(self):
        for split in ((5, 5, 5), (-1, 9, 2), (10,)):
            with self.assertRaises(tactical.IllegalAction):
                rounds.PlayStatusPhase(NewState(), {'sol': Choosy(tokens=split)})

    def testFewerTokensInReinforcements(self):
        sol = self.state.Player('sol')
        sol.tactic_tokens, sol.fleet_tokens, sol.strategy_tokens = 8, 5, 2  # 15 of 16
        rounds.PlayStatusPhase(self.state, {'sol': Choosy(tokens=(9, 5, 2))})
        [event] = [e for e in self.state.log.OfKind('command_tokens')
                   if e.details['player'] == 'sol']
        self.assertEqual(event.details['gained'], 1)

    def testShrinkingFleetPoolRemovesShips(self):
        rounds.PlayStatusPhase(self.state, {'sol': Choosy(tokens=(7, 1, 2))})
        home = self.state.board.SystemAt(SOL_HOME)
        self.assertEqual(len([u for u in home.ShipsOf('sol')
                              if u.unit_type != UnitType.FIGHTER]), 1)


class TestPlayRound(unittest.TestCase):
    def testRoundAdvances(self):
        state = NewState()
        rounds.PlayRound(state)
        self.assertEqual((state.round_number, state.phase), (2, game.STRATEGY))
        kinds = [e.kind for e in state.log]
        self.assertIn('round_started', kinds)
        self.assertEqual(state.log.OfKind('phase_skipped')[0].details['phase'], 'strategy')

    def testSaveMidActionPhase(self):
        state = NewState()
        state.phase = game.ACTION
        state.passed = {'letnev'}
        state.Player('sol').victory_points = 3
        loaded = game.FromDict(game.ToDict(state))
        self.assertEqual(loaded.passed, {'letnev'})
        self.assertEqual(loaded.Player('sol').victory_points, 3)
        summary = game.Summary(loaded)
        self.assertIn('Sol): 3 victory points\n', summary)
        self.assertIn('Letnev): 0 victory points, passed', summary)

    def testRandomRounds(self):
        """Random agents through several full rounds, saving as we go."""
        factions = ['sol', 'letnev', 'jolnar', 'sardakk', 'xxcha', 'yssaril']
        for seed in range(6):
            state = game.NewGame(factions, seed=seed)
            from twimp import dice as dice_lib
            dice = dice_lib.Dice(seed=seed)
            players = {p.name: agents.RandomAgent(seed=seed * 10 + i)
                       for i, p in enumerate(state.players)}
            for _ in range(5):
                rounds.PlayRound(state, players, dice)
                state = game.FromDict(game.ToDict(state))
            self.assertEqual(state.round_number, 6)


if __name__ == '__main__':
    unittest.main()
