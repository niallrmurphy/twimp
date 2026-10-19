#!/usr/bin/env python3

import os
import tempfile
import unittest

from twimp import board as board_lib
from twimp import game
from twimp import game_cli
from twimp import limits
from twimp.units import Unit, UnitType

SIX = ['sol', 'letnev', 'jolnar', 'sardakk', 'xxcha', 'yssaril']


class TestFactionData(unittest.TestCase):
    def testHomePlanetsMatchTiles(self):
        for key, data in game.FactionData().items():
            system = board_lib.MakeSystem(data['home_system'])
            self.assertEqual(system.home, data['name'], key)
            names = {p.name for p in system.planets}
            self.assertLessEqual(set(data['starting_units']['planets']), names, key)

    def testStartingUnitsKnown(self):
        for key, data in game.FactionData().items():
            units = dict(data['starting_units']['space'])
            for on_planet in data['starting_units']['planets'].values():
                units.update(on_planet)
            for type_name in units:
                self.assertIn(type_name, UnitType.__members__, key)

    def testSpotChecks(self):
        f = game.FactionData()
        self.assertEqual(f['sol']['starting_units']['space'],
                         {'CARRIER': 2, 'DESTROYER': 1, 'FIGHTER': 3})
        self.assertEqual(f['hacan']['commodities'], 6)
        self.assertEqual(f['muaat']['starting_units']['space'], {'WARSUN': 1, 'FIGHTER': 2})
        self.assertEqual(f['sardakk']['starting_tech'], [])


class TestNewGame(unittest.TestCase):
    def setUp(self):
        self.state = game.NewGame(SIX, seed=1)

    def testPlayers(self):
        self.assertEqual([p.name for p in self.state.players], SIX)
        sol = self.state.Player('sol')
        self.assertEqual((sol.tactic_tokens, sol.fleet_tokens, sol.strategy_tokens),
                         (3, 3, 2))
        self.assertEqual((sol.trade_goods, sol.commodities, sol.max_commodities), (0, 0, 4))
        self.assertEqual(sol.technologies, ['Antimass Deflectors', 'Neural Motivator'])

    def testHomeSystemsAndUnits(self):
        home = self.state.board.SystemAt(self.state.HomeSystem('sol'))
        self.assertEqual(home.tile_id, '1')
        self.assertEqual(game.DescribeUnits(home.UnitsInSpace('sol')),
                         '2 carrier, 1 destroyer, 3 fighter')
        self.assertEqual(game.DescribeUnits(home.planets[0].UnitsOf('sol')),
                         '5 infantry, 1 spacedock')

    def testPlanetsSplitAsOnFactionSheet(self):
        home = self.state.board.SystemAt(self.state.HomeSystem('yssaril'))
        by_name = {p.name: game.DescribeUnits(p.UnitsOf('yssaril')) for p in home.planets}
        self.assertEqual(by_name, {'Retillion': '3 infantry, 1 spacedock',
                                   'Shalloq': '2 infantry, 1 pds'})

    def testHomePlanetsControlledAndReady(self):
        letnev = self.state.Player('letnev')
        planets = letnev.ControlledPlanets(self.state.board)
        self.assertEqual(sorted(p.name for p in planets), ['Arc Prime', 'Wren Terra'])
        self.assertEqual(letnev.ReadyPlanets(self.state.board), planets)

    def testStartingUnitsWithinLimits(self):
        """Every supported faction's starting units fit capacity and fleet pool."""
        factions = sorted(game.FactionData())
        # The open sample map seats six, so check them six at a time.
        for i in range(0, len(factions), 6):
            batch = factions[i:i + 6]
            if len(batch) < 2:
                batch = factions[i - 1:i + 6]
            state = game.NewGame(batch, game_cli.OPEN_SAMPLE_MAP, seed=1)
            for player in state.players:
                system = state.board.SystemAt(state.HomeSystem(player.name))
                self.assertEqual(limits.CapacityExcess(system, player.name), 0, player.name)
                self.assertEqual(limits.FleetPoolExcess(system, player.name,
                                                        player.fleet_tokens), 0, player.name)

    def testSpeakerFromSeed(self):
        self.assertEqual(game.NewGame(SIX, seed=1).speaker, self.state.speaker)
        speakers = {game.NewGame(SIX, seed=s).speaker for s in range(30)}
        self.assertGreater(len(speakers), 1)
        self.assertEqual(game.NewGame(SIX, speaker='xxcha').speaker, 'xxcha')

    def testStartingState(self):
        self.assertEqual((self.state.round_number, self.state.phase), (1, game.STRATEGY))
        self.assertTrue(self.state.custodians)
        [created] = self.state.log.OfKind('game_created')
        self.assertEqual(created.details['factions'], SIX)

    def testHomeSystemsGoInEmptySlots(self):
        state = game.NewGame(['hacan', 'naalu'], game_cli.OPEN_SAMPLE_MAP, seed=1)
        self.assertEqual(state.board.SystemAt(state.HomeSystem('hacan')).tile_id, '16')
        self.assertEqual(state.HomeSystem('naalu'), board_lib.hexes.Ring(3)[3])

    def testSetupErrors(self):
        for factions in (['sol'], ['sol', 'sol'], ['sol', 'saar'], ['sol', 'nobody']):
            with self.assertRaises(game.SetupError):
                game.NewGame(factions)
        with self.assertRaises(game.SetupError):
            game.NewGame(['sol', 'letnev'], speaker='hacan')
        with self.assertRaises(game.SetupError):
            # The sample map has no room for a seventh home system.
            game.NewGame(SIX + ['hacan'])

    def testSummary(self):
        text = game.Summary(self.state)
        self.assertIn('Speaker: %s' % self.state.speaker, text)
        self.assertIn('Custodians token on Mecatol Rex', text)
        self.assertIn('Arc Prime 4/0', text)
        self.assertIn('1H    Jord         sol: 5 infantry, 1 spacedock', text)


class TestSaveLoad(unittest.TestCase):
    def testRoundTrip(self):
        state = game.NewGame(SIX, seed=2)
        # Change some things that aren't true at setup.
        home = state.board.SystemAt(state.HomeSystem('letnev'))
        home.ShipsOf('letnev')[0].damaged = True
        home.planets[0].exhausted = True
        state.Player('letnev').trade_goods = 3
        state.custodians = False
        state.Log('test_event', note='hello')
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'game.json')
            game.Save(state, path)
            loaded = game.Load(path)
        self.assertEqual(game.ToDict(loaded), game.ToDict(state))
        self.assertEqual(game.Summary(loaded), game.Summary(state))
        self.assertIn('damaged', game.Summary(loaded))
        self.assertEqual(loaded.log.OfKind('test_event')[0].details, {'note': 'hello'})

    def testRejectsUnknownFormat(self):
        d = game.ToDict(game.NewGame(SIX, seed=1))
        d['format'] = 99
        with self.assertRaises(ValueError):
            game.FromDict(d)


if __name__ == '__main__':
    unittest.main()
