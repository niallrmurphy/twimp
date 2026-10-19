#!/usr/bin/env python3
# Players, the overall game state, and setting up a new game.
#
# Players are identified by name (a string) everywhere units are stored, so
# the board, planets and combat code only ever see names. The Player object
# holds everything else about them.

import collections
import dataclasses
import json
import os
import random
from typing import Any, Dict, List

from twimp import board as board_lib
from twimp import hexes
from twimp.units import Unit, UnitType

FACTIONS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'factions.json')

STARTING_TACTIC_TOKENS = 3
STARTING_FLEET_TOKENS = 3
STARTING_STRATEGY_TOKENS = 2
COMMAND_TOKENS_PER_PLAYER = 16
MAX_PLAYERS = 8

# Game phases, in round order.
STRATEGY, ACTION, STATUS, AGENDA = 'strategy', 'action', 'status', 'agenda'


class SetupError(Exception):
    pass


_factions = None


def FactionData():
    """The faction definitions from data/factions.json, keyed by short name."""
    global _factions
    if _factions is None:
        with open(FACTIONS_FILE) as f:
            _factions = json.load(f)['factions']
    return _factions


@dataclasses.dataclass
class Player(object):
    name: str
    faction: str
    tactic_tokens: int = STARTING_TACTIC_TOKENS
    fleet_tokens: int = STARTING_FLEET_TOKENS
    strategy_tokens: int = STARTING_STRATEGY_TOKENS
    trade_goods: int = 0
    commodities: int = 0
    technologies: List[str] = dataclasses.field(default_factory=list)

    @property
    def faction_data(self):
        return FactionData()[self.faction]

    @property
    def max_commodities(self):
        return self.faction_data['commodities']

    def ControlledPlanets(self, board):
        """Planets this player controls. Control lives on the planets, so
        this is worked out from the board rather than stored here."""
        return [p for s in board.systems.values() for p in s.planets
                if p.controller == self.name]

    def ReadyPlanets(self, board):
        return [p for p in self.ControlledPlanets(board) if not p.exhausted]


@dataclasses.dataclass
class Event(object):
    round_number: int
    phase: str
    kind: str
    details: Dict[str, Any] = dataclasses.field(default_factory=dict)


class EventLog(object):
    """An append-only record of what happened, for debugging and replays."""
    def __init__(self, events=None):
        self.events = list(events or [])

    def Append(self, event):
        self.events.append(event)

    def __iter__(self):
        return iter(self.events)

    def __len__(self):
        return len(self.events)

    def OfKind(self, kind):
        return [e for e in self.events if e.kind == kind]


class GameState(object):
    def __init__(self, board, players, speaker, round_number=1, phase=STRATEGY,
                 custodians=True, log=None):
        self.board = board
        self.players = list(players)
        self.speaker = speaker
        self.round_number = round_number
        self.phase = phase
        # Whether the custodians token is still on Mecatol Rex.
        self.custodians = custodians
        self.log = log or EventLog()

    def Log(self, kind, **details):
        self.log.Append(Event(self.round_number, self.phase, kind, details))

    def Player(self, name):
        for player in self.players:
            if player.name == name:
                return player
        raise KeyError(name)

    def HomeSystem(self, name):
        """The coordinates of a player's home system."""
        return self.board.Find(self.Player(name).faction_data['home_system'])

    def CommandTokensOnBoard(self, name):
        return [c for c, s in self.board.systems.items() if name in s.command_tokens]

    def ReinforcementTokens(self, name):
        """Command tokens neither in the player's pools nor on the board."""
        p = self.Player(name)
        return (COMMAND_TOKENS_PER_PLAYER - p.tactic_tokens - p.fleet_tokens
                - p.strategy_tokens - len(self.CommandTokensOnBoard(name)))

    def UnitsOnBoard(self, name, unit_type):
        """How many of a player's units of a type are on the board, for
        plastic limits."""
        count = 0
        for system in self.board.systems.values():
            count += sum(1 for u in system.space.get(name, []) if u.unit_type == unit_type)
            for planet in system.planets:
                count += sum(1 for u in planet.units.get(name, [])
                             if u.unit_type == unit_type)
        return count


def _HomeSlots(board):
    """Empty outer-ring positions where home systems can go, in order."""
    radius = max(hexes.Distance(hexes.CENTER, c) for c in board.systems)
    return [c for c in hexes.Ring(radius) if c not in board.systems]


def NewGame(factions, map_string=board_lib.SAMPLE_MAP, speaker=None, seed=None):
    """Set up a game: board, players, home systems and starting units.

    Args:
      factions: faction short names (keys of data/factions.json), in seat
        order. Each player is named after their faction.
      map_string: the map. A faction's home system is used where the map
        already has it; otherwise it goes in the next empty outer-ring slot.
      speaker: the speaker's name; chosen at random (from seed) if None.
    """
    if not 2 <= len(factions) <= MAX_PLAYERS:
        raise SetupError("A game needs 2 to %d players" % MAX_PLAYERS)
    if len(set(factions)) != len(factions):
        raise SetupError("Each faction can only be played once")
    for faction in factions:
        if faction not in FactionData():
            raise SetupError("Unknown or unsupported faction %r; choose from %s" % (
                faction, ', '.join(sorted(FactionData()))))
    board = board_lib.Board.FromMapString(map_string)
    slots = _HomeSlots(board)
    players = []
    for faction in factions:
        data = FactionData()[faction]
        player = Player(name=faction, faction=faction,
                        technologies=list(data['starting_tech']))
        players.append(player)
        coord = board.Find(data['home_system'])
        if coord is None:
            if not slots:
                raise SetupError("No room on the map for %s's home system" % faction)
            coord = slots.pop(0)
            board.Place(coord, board_lib.MakeSystem(data['home_system']))
        _PlaceStartingUnits(board.SystemAt(coord), player.name,
                            data['starting_units'])
    if speaker is None:
        speaker = random.Random(seed).choice(factions)
    elif speaker not in factions:
        raise SetupError("Speaker %r isn't playing" % speaker)
    state = GameState(board, players, speaker)
    state.Log('game_created', factions=list(factions), map=map_string,
              speaker=speaker)
    return state


def _PlaceStartingUnits(system, player, starting_units):
    """Ships go in space; ground forces and structures on the named home
    planets, which the player controls and which start ready."""
    for type_name, count in starting_units['space'].items():
        for _ in range(count):
            system.AddUnit(player, Unit(UnitType[type_name]))
    planets = {p.name: p for p in system.planets}
    for planet in system.planets:
        planet.controller = player
        planet.exhausted = False
    for planet_name, units in starting_units['planets'].items():
        for type_name, count in units.items():
            for _ in range(count):
                planets[planet_name].AddUnit(player, Unit(UnitType[type_name]))


# Biggest ships first, then ground forces and structures.
DISPLAY_ORDER = ['WARSUN', 'FLAGSHIP', 'DREADNOUGHT', 'CARRIER', 'CRUISER',
                 'DESTROYER', 'FIGHTER', 'INFANTRY', 'PDS', 'SPACEDOCK']


def DescribeUnits(units):
    """e.g. '2 carrier, 1 destroyer, 3 fighter'."""
    counts = collections.Counter(u.unit_type.name for u in units)
    damaged = collections.Counter(u.unit_type.name for u in units if u.damaged)
    parts = []
    for name in DISPLAY_ORDER:
        if counts[name]:
            text = '%d %s' % (counts[name], name.lower())
            if damaged[name]:
                text += ' (%d damaged)' % damaged[name]
            parts.append(text)
    return ', '.join(parts)


def Summary(state):
    """A readable overview of the game state."""
    lines = ['Round %d, %s phase. Speaker: %s.%s' % (
        state.round_number, state.phase, state.speaker,
        ' Custodians token on Mecatol Rex.' if state.custodians else '')]
    lines.append('')
    for player in state.players:
        planets = player.ControlledPlanets(state.board)
        lines.append('%s (%s)' % (player.name, player.faction_data['name']))
        lines.append('  command tokens: %d tactic, %d fleet, %d strategy' % (
            player.tactic_tokens, player.fleet_tokens, player.strategy_tokens))
        lines.append('  trade goods %d, commodities %d/%d' % (
            player.trade_goods, player.commodities, player.max_commodities))
        lines.append('  technologies: %s' % (', '.join(player.technologies) or 'none'))
        lines.append('  planets: %s' % ', '.join(
            '%s %d/%d%s' % (p.name, p.resources, p.influence,
                            ' (exhausted)' if p.exhausted else '')
            for p in planets))
    tokens = ['%s: %s' % (s.Label(), ', '.join(sorted(s.command_tokens)))
              for c in hexes.Spiral(10)
              for s in [state.board.SystemAt(c)] if s is not None and s.command_tokens]
    if tokens:
        lines.append('')
        lines.append('Command tokens on the board: %s' % '; '.join(tokens))
    lines.append('')
    lines.append('Units:')
    for coord in hexes.Spiral(10):
        system = state.board.SystemAt(coord)
        if system is None:
            continue
        for player, units in system.space.items():
            if units:
                lines.append('  %-5s space        %s: %s' % (
                    system.Label(), player, DescribeUnits(units)))
        for planet in system.planets:
            for player, units in planet.units.items():
                if units:
                    lines.append('  %-5s %-12s %s: %s' % (
                        system.Label(), planet.name, player, DescribeUnits(units)))
    return '\n'.join(lines) + '\n'


# Saving and loading. The format stores tile ids rather than tile contents:
# planets come from the tile data, and only what changes during a game
# (control, exhaustion, units) is saved.

SAVE_FORMAT = 1


def _UnitToDict(unit):
    d = {'type': unit.unit_type.name}
    if unit.damaged:
        d['damaged'] = True
    if unit.cargo:
        d['cargo'] = [_UnitToDict(u) for u in unit.cargo]
    return d


def _UnitFromDict(d):
    unit = Unit(UnitType[d['type']])
    unit.damaged = d.get('damaged', False)
    unit.cargo = [_UnitFromDict(c) for c in d.get('cargo', [])]
    return unit


def _UnitsToDict(units_by_player):
    return {p: [_UnitToDict(u) for u in units]
            for p, units in units_by_player.items() if units}


def _UnitsFromDict(d):
    return {p: [_UnitFromDict(u) for u in units] for p, units in d.items()}


def ToDict(state):
    systems = []
    for coord in hexes.Spiral(10):
        system = state.board.SystemAt(coord)
        if system is None:
            continue
        systems.append({
            'q': coord.q, 'r': coord.r, 'tile': system.tile_id,
            'space': _UnitsToDict(system.space),
            'command_tokens': sorted(system.command_tokens),
            'planets': [{'name': p.name, 'controller': p.controller,
                         'exhausted': p.exhausted,
                         'units': _UnitsToDict(p.units)}
                        for p in system.planets],
        })
    return {
        'format': SAVE_FORMAT,
        'round': state.round_number,
        'phase': state.phase,
        'speaker': state.speaker,
        'custodians': state.custodians,
        'players': [dataclasses.asdict(p) for p in state.players],
        'systems': systems,
        'log': [dataclasses.asdict(e) for e in state.log],
    }


def FromDict(d):
    if d.get('format') != SAVE_FORMAT:
        raise ValueError("Unsupported save format %r" % d.get('format'))
    board = board_lib.Board()
    for s in d['systems']:
        system = board_lib.MakeSystem(s['tile'])
        system.space = _UnitsFromDict(s['space'])
        system.command_tokens = set(s.get('command_tokens', []))
        if [p['name'] for p in s['planets']] != [p.name for p in system.planets]:
            raise ValueError("Saved planets don't match tile %s" % s['tile'])
        for planet, saved in zip(system.planets, s['planets']):
            planet.controller = saved['controller']
            planet.exhausted = saved['exhausted']
            planet.units = _UnitsFromDict(saved['units'])
        board.Place(hexes.Hex(s['q'], s['r']), system)
    return GameState(board,
                     [Player(**p) for p in d['players']],
                     d['speaker'],
                     round_number=d['round'],
                     phase=d['phase'],
                     custodians=d['custodians'],
                     log=EventLog(Event(**e) for e in d['log']))


def Save(state, path):
    with open(path, 'w') as f:
        json.dump(ToDict(state), f, indent=1)
        f.write('\n')


def Load(path):
    with open(path) as f:
        return FromDict(json.load(f))
