#!/usr/bin/env python3

import unittest

from twimp import agents
from twimp import dice as dice_lib
from twimp import game
from twimp import hexes
from twimp import limits
from twimp import tactical
from twimp.units import Unit, UnitType
from tests.fakes import ScriptedDice

# Sol's home directly north of Mecatol Rex, Lodor (alpha wormhole, 3/1) to
# the north-east, Letnev's home to the south-east, and three empty systems.
MAP = '{18} 1 26 10 46 47 48'
SOL_HOME, LODOR, LETNEV_HOME = hexes.NORTH, hexes.NORTH_EAST, hexes.SOUTH_EAST
MECATOL = hexes.CENTER

INF, FTR = UnitType.INFANTRY, UnitType.FIGHTER


class Scripted(agents.GreedyAgent):
    """GreedyAgent, with any choice optionally replaced."""
    def __init__(self, activate=None, move=None, produce=None, retreat=False):
        self.activate, self.move, self.produce, self.retreat = activate, move, produce, retreat

    def ChooseActivation(self, state, player, options):
        if self.activate is None:
            return super(Scripted, self).ChooseActivation(state, player, options)
        return self.activate

    def ChooseMovement(self, state, player, active, options, transportable):
        if self.move is None:
            return super(Scripted, self).ChooseMovement(state, player, active, options,
                                                        transportable)
        return self.move(options, transportable)

    def ChooseProduction(self, state, player, coord, context):
        if self.produce is None:
            return super(Scripted, self).ChooseProduction(state, player, coord, context)
        return self.produce

    def DeclareRetreat(self, own_units, enemy_units, round_number):
        return self.retreat


def CarrierAndDestroyer(infantry=2):
    """Move one carrier carrying `infantry` ground forces, plus the destroyer."""
    def Move(options, transportable):
        carrier = next(o for o in options if o.ship.unit_type == UnitType.CARRIER)
        destroyer = next(o for o in options if o.ship.unit_type == UnitType.DESTROYER)
        ground = [u for u in transportable[carrier.start] if u.IsGroundForce()]
        return [(carrier, ground[:infantry]), (destroyer, [])]
    return Move


def NewState():
    return game.NewGame(['sol', 'letnev'], MAP, speaker='sol')


class TacticalTest(unittest.TestCase):
    def setUp(self):
        self.state = NewState()

    def System(self, coord):
        return self.state.board.SystemAt(coord)

    def Act(self, player='sol', rolls=(), **agents_by_player):
        dice = ScriptedDice(rolls)
        report = tactical.TakeTacticalAction(self.state, player, agents_by_player, dice)
        self.assertEqual(dice.rolls, [], 'unused scripted rolls')
        return report

    def Count(self, units, unit_type):
        return sum(1 for u in units if u.unit_type == unit_type)


class TestActivationAndMovement(TacticalTest):
    def testGreedyTakesLodor(self):
        report = self.Act()
        self.assertEqual(report.active, LODOR)
        lodor = self.System(LODOR)
        self.assertEqual(lodor.planets[0].controller, 'sol')
        self.assertTrue(lodor.planets[0].exhausted)
        self.assertEqual(lodor.command_tokens, {'sol'})
        self.assertEqual(self.state.Player('sol').tactic_tokens, 2)
        self.assertEqual(len(report.moves), 3)
        # One infantry is left at home.
        self.assertEqual(len(self.System(SOL_HOME).planets[0].GroundForces('sol')), 1)
        kinds = [e.kind for e in self.state.log]
        self.assertEqual(kinds.count('moved'), 3)
        self.assertIn('planet_gained', kinds)

    def testNoTacticTokens(self):
        self.state.Player('sol').tactic_tokens = 0
        with self.assertRaises(tactical.IllegalAction):
            self.Act()

    def testCantActivateSystemWithOwnToken(self):
        self.System(LODOR).command_tokens.add('sol')
        self.assertNotIn(LODOR, tactical.ActivationOptions(self.state, 'sol'))
        with self.assertRaises(tactical.IllegalAction):
            self.Act(sol=Scripted(activate=LODOR))

    def testShipsCantLeaveSystemsWithOwnToken(self):
        self.System(SOL_HOME).command_tokens.add('sol')
        self.System(LODOR).command_tokens.add('letnev')  # irrelevant to sol
        self.assertEqual(tactical.MoveOptions(self.state, 'sol', LODOR), [])

    def testMovementValidation(self):
        stranger = Unit(INF)
        bad_moves = [
            lambda o, t: [(o[0], []), (o[0], [])],                       # same ship twice
            lambda o, t: [(o[0], [u for u in t[o[0].start]][:5])],       # over capacity
            lambda o, t: [(o[0], [stranger])],                           # not available
            lambda o, t: [(tactical.MoveOption(Unit(UnitType.CRUISER), SOL_HOME,
                                               o[0].path), [])],         # made-up option
        ]
        for move in bad_moves:
            self.state = NewState()
            with self.assertRaises(tactical.IllegalAction):
                self.Act(sol=Scripted(activate=LODOR, move=move))

    def testUnitsLeftBehindAreLost(self):
        home = self.System(SOL_HOME)
        home.AddUnit('sol', Unit(INF))
        home.AddUnit('sol', Unit(INF))

        def MoveShipsOnly(options, transportable):
            return [(o, []) for o in options]

        report = self.Act(sol=Scripted(activate=LODOR, move=MoveShipsOnly))
        # The 3 fighters left behind are covered by the space dock; the 2
        # infantry in space are not.
        self.assertEqual([u.unit_type for u in report.left_behind], [INF, INF])
        self.assertEqual(self.Count(home.UnitsInSpace('sol'), FTR), 3)


class TestCombatAndInvasion(TacticalTest):
    def testSpaceCombatThenInvasion(self):
        self.System(LODOR).AddUnit('letnev', Unit(UnitType.DESTROYER))
        report = self.Act(sol=Scripted(activate=LODOR, move=CarrierAndDestroyer()),
                          rolls=[9, 1,   # sol: carrier hits, destroyer misses
                                 1])     # letnev's destroyer misses
        self.assertEqual(report.defender, 'letnev')
        self.assertEqual(report.space_combat.winner, 'attacker')
        self.assertEqual(self.System(LODOR).ShipsOf('letnev'), [])
        self.assertEqual(self.System(LODOR).planets[0].controller, 'sol')
        [event] = self.state.log.OfKind('space_combat')
        self.assertEqual(event.details['winner'], 'sol')

    def testSpaceCannonOffenseAndDefense(self):
        lodor = self.System(LODOR).planets[0]
        lodor.controller = 'letnev'
        lodor.AddUnit('letnev', Unit(UnitType.PDS))
        lodor.AddUnit('letnev', Unit(INF))
        report = self.Act(sol=Scripted(activate=LODOR, move=CarrierAndDestroyer()),
                          rolls=[6,      # space cannon offense: hits sol's destroyer
                                 1,      # space cannon defense: misses
                                 8, 1,   # ground combat: sol hits once
                                 1])     # letnev misses
        [shot] = report.space_cannon
        self.assertEqual((shot.shooter, shot.target, shot.hits), ('letnev', 'sol', 1))
        self.assertEqual([u.unit_type for u in shot.losses], [UnitType.DESTROYER])
        self.assertIsNone(report.space_combat)
        self.assertEqual(lodor.controller, 'sol')
        # The captured PDS is destroyed.
        self.assertEqual(lodor.UnitsOf('letnev'), [])

    def testDefenderRetreatsHome(self):
        self.System(LODOR).AddUnit('letnev', Unit(UnitType.DESTROYER))
        report = self.Act(sol=Scripted(activate=LODOR, move=CarrierAndDestroyer()),
                          letnev=Scripted(retreat=True),
                          rolls=[1, 1, 1])   # everyone misses; letnev retreats
        self.assertEqual(report.space_combat.retreated, 'defender')
        self.assertEqual(report.retreated_to, LETNEV_HOME)
        self.assertIn('letnev', self.System(LETNEV_HOME).command_tokens)
        # Letnev's home already has 3 non-fighter ships and Letnev has 3 fleet
        # tokens, so one of the two destroyers there now has to go.
        self.assertEqual(self.Count(self.System(LETNEV_HOME).ShipsOf('letnev'),
                                    UnitType.DESTROYER), 1)
        self.assertEqual(len(self.state.log.OfKind('fleet_pool_exceeded')), 1)
        # With the defender gone, sol invades.
        self.assertEqual(self.System(LODOR).planets[0].controller, 'sol')

    def testRetreatWithRoomInFleetPool(self):
        self.System(LODOR).AddUnit('letnev', Unit(UnitType.DESTROYER))
        self.state.Player('letnev').fleet_tokens = 4
        self.Act(sol=Scripted(activate=LODOR, move=CarrierAndDestroyer()),
                 letnev=Scripted(retreat=True), rolls=[1, 1, 1])
        self.assertEqual(self.Count(self.System(LETNEV_HOME).ShipsOf('letnev'),
                                    UnitType.DESTROYER), 2)

    def testNoRetreatWithoutSomewhereToGo(self):
        self.System(LODOR).AddUnit('letnev', Unit(UnitType.DESTROYER))
        # Sol ships in Letnev's home: Letnev's only retreat option is gone.
        self.System(LETNEV_HOME).AddUnit('sol', Unit(UnitType.CRUISER))
        self.assertEqual(tactical.RetreatOptions(self.state, 'letnev', LODOR), [])
        report = self.Act(sol=Scripted(activate=LODOR, move=CarrierAndDestroyer()),
                          letnev=Scripted(retreat=True),
                          rolls=[1, 1, 1,    # round 1: all miss
                                 9, 1, 1])   # round 2: sol's carrier hits
        self.assertIsNone(report.space_combat.retreated)
        self.assertEqual(len(report.space_combat.rounds), 2)

    def testGravityRift(self):
        # Sol's carrier (move 1) can only reach Lodor through the rift.
        self.state = game.NewGame(['sol', 'letnev'], '{18} 1 41 26 10 0 0', speaker='sol')
        target = hexes.SOUTH_EAST

        def CarrierOnly(options, transportable):
            carrier = next(o for o in options if o.ship.unit_type == UnitType.CARRIER)
            self.assertEqual(carrier.path.rifts_exited, 1)
            ground = [u for u in transportable[carrier.start] if u.IsGroundForce()]
            return [(carrier, ground[:2])]

        report = self.Act(sol=Scripted(activate=target, move=CarrierOnly), rolls=[3])
        self.assertEqual(sorted(u.unit_type.name for u in report.rift_losses),
                         ['CARRIER', 'INFANTRY', 'INFANTRY'])
        self.assertEqual(self.System(target).UnitsInSpace('sol'), [])
        self.assertEqual(len(self.state.log.OfKind('destroyed_by_gravity_rift')), 1)

        self.state = game.NewGame(['sol', 'letnev'], '{18} 1 41 26 10 0 0', speaker='sol')
        self.Act(sol=Scripted(activate=target, move=CarrierOnly), rolls=[4])
        self.assertEqual(self.System(target).planets[0].controller, 'sol')

    def testNoLandingOnMecatolWhileCustodiansThere(self):
        def CarrierWithInfantry(options, transportable):
            carrier = next(o for o in options if o.ship.unit_type == UnitType.CARRIER)
            ground = [u for u in transportable[carrier.start] if u.IsGroundForce()]
            return [(carrier, ground[:2])]

        self.Act(sol=Scripted(activate=MECATOL, move=CarrierWithInfantry))
        mecatol = self.System(MECATOL)
        self.assertIsNone(mecatol.planets[0].controller)
        self.assertEqual(self.Count(mecatol.UnitsInSpace('sol'), INF), 2)

        self.state = NewState()
        self.state.custodians = False
        self.Act(sol=Scripted(activate=MECATOL, move=CarrierWithInfantry))
        self.assertEqual(self.System(MECATOL).planets[0].controller, 'sol')


class TestListener(TacticalTest):
    def testCombatsReportWhereAndWho(self):
        lodor = self.System(LODOR)
        lodor.AddUnit('letnev', Unit(UnitType.DESTROYER))
        lodor.planets[0].controller = 'letnev'
        lodor.planets[0].AddUnit('letnev', Unit(INF))
        heard = []

        def Listen(event, **details):
            if event == 'start':
                heard.append({k: details.get(k) for k in
                              ('kind', 'system', 'planet', 'attacker', 'defender')})

        dice = ScriptedDice([9, 1, 1,      # space combat: sol's carrier hits
                             8, 1, 1])     # ground combat: sol hits, letnev misses
        tactical.TakeTacticalAction(
            self.state, 'sol', {'sol': Scripted(activate=LODOR, move=CarrierAndDestroyer())},
            dice, listener=Listen)
        self.assertEqual(heard, [
            {'kind': 'space', 'system': '26a', 'planet': None,
             'attacker': 'sol', 'defender': 'letnev'},
            {'kind': 'ground', 'system': '26a', 'planet': 'Lodor',
             'attacker': 'sol', 'defender': 'letnev'}])


class TestProduction(TacticalTest):
    def testProduceAtHome(self):
        report = self.Act(sol=Scripted(activate=SOL_HOME, produce={INF: 4, FTR: 2}))
        self.assertEqual(report.moves, [])
        self.assertEqual(report.produced, {INF: 4, FTR: 2})
        jord = self.System(SOL_HOME).planets[0]
        self.assertTrue(jord.exhausted)
        self.assertEqual(report.paid_planets, ['Jord'])
        self.assertEqual(len(jord.GroundForces('sol')), 9)
        self.assertEqual(self.Count(self.System(SOL_HOME).UnitsInSpace('sol'), FTR), 5)
        [event] = self.state.log.OfKind('produced')
        self.assertEqual(event.details['cost'], 3)

    def testGreedyBuildsInfantryWhenFleetPoolIsFull(self):
        report = self.Act(sol=Scripted(activate=SOL_HOME))
        # Fleet pool is full (2 carriers + destroyer), so no cruiser; Jord's
        # 4 resources buy 6 infantry (the production limit is 4 + 2).
        self.assertEqual(report.produced, {INF: 6})

    def testProductionRules(self):
        def Exhausted(state):
            state.board.SystemAt(SOL_HOME).planets[0].exhausted = True

        def Blockaded(state):
            home = state.board.SystemAt(SOL_HOME)
            home.space['sol'] = []
            home.AddUnit('letnev', Unit(UnitType.DESTROYER))

        cases = [
            ({UnitType.CRUISER: 1}, None),        # fleet pool is full
            ({INF: 7}, None),                     # over the production limit of 6
            ({INF: 2}, Exhausted),                # nothing to pay with
            ({UnitType.PDS: 1}, None),            # structures can't be produced
            ({UnitType.WARSUN: 1}, None),         # needs the War Sun technology
            ({FTR: 2}, Blockaded),                # blockaded: no ships
        ]
        for choice, prepare in cases:
            self.state = NewState()
            if prepare:
                prepare(self.state)
            with self.assertRaises(tactical.IllegalAction, msg=str(choice)):
                self.Act(sol=Scripted(activate=SOL_HOME, produce=choice))

    def testBlockadedDockCanStillProduceGroundForces(self):
        home = self.System(SOL_HOME)
        home.space['sol'] = []
        home.AddUnit('letnev', Unit(UnitType.DESTROYER))
        report = self.Act(sol=Scripted(activate=SOL_HOME, produce={INF: 2}))
        self.assertEqual(report.produced, {INF: 2})

    def testPayResourcesWastesLeast(self):
        board = self.state.board
        for coord in (LODOR, MECATOL):
            board.SystemAt(coord).planets[0].controller = 'sol'
        sol = self.state.Player('sol')
        sol.trade_goods = 2
        # Jord 4, Lodor 3, Mecatol Rex 1, and 2 trade goods.
        cases = [(3, ['Lodor'], 0), (5, ['Jord', 'Mecatol Rex'], 0),
                 (8, ['Jord', 'Lodor', 'Mecatol Rex'], 0)]
        for cost, planets, trade_goods in cases:
            for planet in sol.ControlledPlanets(board):
                planet.exhausted = False
            paid = tactical.PayResources(self.state, 'sol', cost)
            self.assertEqual((sorted(paid[0]), paid[1]), (sorted(planets), trade_goods), cost)
        for planet in sol.ControlledPlanets(board):
            planet.exhausted = False
        self.assertEqual(tactical.PayResources(self.state, 'sol', 10)[1], 2)
        self.assertEqual(sol.trade_goods, 0)
        with self.assertRaises(tactical.IllegalAction):
            tactical.PayResources(self.state, 'sol', 1)


class TestReport(TacticalTest):
    def testDescribeReport(self):
        self.System(LODOR).AddUnit('letnev', Unit(UnitType.DESTROYER))
        report = self.Act(sol=Scripted(activate=LODOR, move=CarrierAndDestroyer()),
                          rolls=[9, 1, 1])
        text = tactical.DescribeReport(self.state, report)
        self.assertIn('sol activates 26a (Lodor).', text)
        self.assertIn('moves carrier from 1H (1H > 26a) carrying 2 infantry', text)
        self.assertIn('space combat with letnev: 1 round(s), won by sol', text)
        self.assertIn('Lodor: lands 2 infantry, takes control', text)


class TestRandomPlay(unittest.TestCase):
    """Random agents try everything; the board must stay legal throughout."""

    def testRandomGamesStayLegal(self):
        factions = ['sol', 'letnev', 'jolnar', 'sardakk', 'xxcha', 'yssaril']
        for seed in range(12):
            state = game.NewGame(factions, seed=seed)
            dice = dice_lib.Dice(seed=seed)
            players = {p.name: agents.RandomAgent(seed=seed * 10 + i)
                       for i, p in enumerate(state.players)}
            for _ in range(4):
                for _ in range(3):
                    for p in state.players:
                        report = tactical.TakeTacticalAction(state, p.name, players, dice)
                        self.assertLessEqual(
                            len(state.board.SystemAt(report.active).PlayersWithShips()), 1)
                        for system in state.board.systems.values():
                            for q in state.players:
                                self.assertEqual(limits.CapacityExcess(system, q.name), 0)
                                self.assertEqual(limits.FleetPoolExcess(
                                    system, q.name, q.fleet_tokens), 0)
                # Stand-in for the status phase, which doesn't exist yet.
                for system in state.board.systems.values():
                    system.command_tokens.clear()
                    for planet in system.planets:
                        planet.exhausted = False
                for p in state.players:
                    p.tactic_tokens = 3
            self.assertEqual(game.ToDict(game.FromDict(game.ToDict(state))),
                             game.ToDict(state))


if __name__ == '__main__':
    unittest.main()
