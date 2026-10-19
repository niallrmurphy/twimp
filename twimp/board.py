#!/usr/bin/env python3
# The galaxy: planets, systems (one per tile) and the board of systems.

import enum
import json
import os

from twimp import hexes

TILES_FILE = os.path.join(os.path.dirname(__file__), 'data', 'tiles.json')
MECATOL_REX = '18'

# A 6-player map using only base game tiles, with home systems in the usual
# places (every third tile of the outer ring). Not balanced, just valid.
SAMPLE_MAP = ('19 26 20 21 41 22 '
              '23 24 42 25 27 28 29 43 30 31 44 32 '
              '1 33 34 10 35 36 12 37 38 13 39 45 14 40 46 15 47 48')


class CannotPerformException(Exception):
  pass


class Anomaly(enum.Enum):
  ASTEROID_FIELD = 'asteroid_field'
  GRAVITY_RIFT = 'gravity_rift'
  NEBULA = 'nebula'
  SUPERNOVA = 'supernova'


class Planet(object):
  """A TI4 planet. We won't bother with accessors/mutators for most of this."""
  def __init__(self,
               name,
               resources,
               influence,
               trait=None,
               tech_specialty=None):
    if name is None:
      raise CannotPerformException("Can't have a planet without a name")
    else:
      self.name = name
    if resources is None:
      raise CannotPerformException("Can't have a planet without defined resources")
    else:
      self.resources = resources
    if influence is None:
      raise CannotPerformException("Can't have a planet without defined influence")
    else:
      self.influence = influence
    # 'cultural', 'hazardous', 'industrial' or None (e.g. home planets).
    self.trait = trait
    # 'biotic', 'cybernetic', 'propulsion', 'warfare' or None.
    self.tech_specialty = tech_specialty
    # The player who controls the planet (holds its card), or None.
    self.controller = None
    self.exhausted = False
    # Ground forces and structures on the planet: {player: [Unit, ...]}.
    self.units = {}

  def __repr__(self):
    return "<Planet %s>" % self.name

  def GainControl(self, player):
    """Give control to a player. A newly gained planet's card is exhausted."""
    if self.controller != player:
      self.controller = player
      self.exhausted = True

  def SwitchOwner(self, owner):
    self.GainControl(owner)

  def IsNeutral(self):
    """Neutral planets are those that are not controlled by a player."""
    return self.controller is None

  def AddUnit(self, player, unit):
    self.units.setdefault(player, []).append(unit)

  def UnitsOf(self, player):
    """The live list of a player's units here; mutating it changes the planet."""
    return self.units.setdefault(player, [])

  def GroundForces(self, player):
    return [u for u in self.units.get(player, []) if u.IsGroundForce()]

  def Structures(self, player):
    return [u for u in self.units.get(player, []) if u.IsStructure()]

  def OtherPlayers(self, player):
    """Other players with units on this planet."""
    return [p for p, units in self.units.items() if p != player and units]

  def IsEmpty(self):
    """Empty planets are those with no ground forces on them."""
    return not any(u.IsGroundForce()
                   for units in self.units.values() for u in units)

  def RemoveUnits(self, player, to_remove):
    self.units[player] = [u for u in self.units.get(player, [])
                          if all(u is not r for r in to_remove)]


class System(object):
  """One system tile on the board: its planets, wormholes, anomaly, and
  each player's units in its space area."""
  def __init__(self, tile_id, planets=None, wormholes=(), anomaly=None,
               home=None, name=None):
    self.tile_id = str(tile_id)
    self.planets = list(planets or [])
    self.wormholes = frozenset(wormholes)
    self.anomaly = anomaly
    # The faction whose home system this is, or None.
    self.home = home
    self.name = name
    # Units in the space area: {player: [Unit, ...]}. Ships, plus any
    # fighters and ground forces they carry.
    self.space = {}

  def __repr__(self):
    return "<System %s>" % self.tile_id

  def AddUnit(self, player, unit):
    self.space.setdefault(player, []).append(unit)

  def UnitsInSpace(self, player):
    """The live list of a player's units in space here."""
    return self.space.setdefault(player, [])

  def ShipsOf(self, player):
    return [u for u in self.space.get(player, []) if u.IsShip()]

  def PlayersWithShips(self):
    return [p for p in self.space if self.ShipsOf(p)]

  def HasOtherPlayersShips(self, player):
    return any(p != player for p in self.PlayersWithShips())

  def TotalResources(self):
    return sum(p.resources for p in self.planets)

  def TotalInfluence(self):
    return sum(p.influence for p in self.planets)

  def Label(self):
    """A short label for maps: tile id, plus a marker for wormholes
    (a, b, d), anomalies (A, G, N, S) or a home system (H)."""
    marks = ''.join(w[0] for w in sorted(self.wormholes))
    if self.anomaly is not None:
      marks += {Anomaly.ASTEROID_FIELD: 'A', Anomaly.GRAVITY_RIFT: 'G',
                Anomaly.NEBULA: 'N', Anomaly.SUPERNOVA: 'S'}[self.anomaly]
    if self.home:
      marks += 'H'
    return self.tile_id + marks


_tiles = None


def TileData():
  """The tile definitions from data/tiles.json, keyed by tile id."""
  global _tiles
  if _tiles is None:
    with open(TILES_FILE) as f:
      _tiles = json.load(f)['tiles']
  return _tiles


def MakeSystem(tile_id):
  """A fresh System (with fresh Planets) for a tile id."""
  spec = TileData().get(str(tile_id))
  if spec is None:
    raise CannotPerformException(
        "Unknown tile %r (only base game tiles 1-50 are supported)" % (tile_id,))
  planets = [Planet(name, r, i, trait, specialty)
             for name, r, i, trait, specialty in spec.get('planets', [])]
  anomaly = Anomaly(spec['anomaly']) if spec.get('anomaly') else None
  return System(tile_id, planets, spec.get('wormholes', ()), anomaly,
                spec.get('home'), spec.get('name'))


class Board(object):
  """Systems placed on a hex grid, keyed by hexes.Hex coordinates."""
  def __init__(self):
    self.systems = {}

  @classmethod
  def FromMapString(cls, map_string):
    """Build a board from a map string: space-separated tile ids, ring by
    ring from the tile directly above the centre, clockwise.

    Mecatol Rex is placed at the centre unless the string starts with a
    centre tile in braces, e.g. '{18}'. A tile id of 0 leaves the position
    empty (e.g. a home system still to be placed).
    """
    board = cls()
    tokens = map_string.split()
    center = MECATOL_REX
    if tokens and tokens[0].startswith('{') and tokens[0].endswith('}'):
      center = tokens.pop(0)[1:-1]
    board.Place(hexes.CENTER, MakeSystem(center))
    radius = 1
    while len(hexes.Spiral(radius)) - 1 < len(tokens):
      radius += 1
    for coord, token in zip(hexes.Spiral(radius)[1:], tokens):
      if token not in ('0', '-1'):
        board.Place(coord, MakeSystem(token))
    return board

  def Place(self, coord, system):
    self.systems[coord] = system

  def SystemAt(self, coord):
    return self.systems.get(coord)

  def Find(self, tile_id):
    """The coordinates of the first system with this tile id, or None."""
    for coord, system in self.systems.items():
      if system.tile_id == str(tile_id):
        return coord
    return None

  def Adjacent(self, coord):
    """Coordinates of systems adjacent to coord: physically next to it, or
    sharing a wormhole type with it."""
    result = [n for n in hexes.Neighbors(coord) if n in self.systems]
    wormholes = self.systems[coord].wormholes
    if wormholes:
      for other, system in self.systems.items():
        if other != coord and other not in result and wormholes & system.wormholes:
          result.append(other)
    return result

  def Render(self, highlight=(), origin=None, width=7, label=None):
    """Draw the board as text, one label per system.

    Systems in `highlight` are shown in [brackets] and `origin` in (parens).
    `label` is a function from System to text (default: System.Label).
    Flat-topped hexes are laid out in columns; neighbours to the north and
    south are two lines apart, and diagonal neighbours one line apart.
    """
    if not self.systems:
      return ''
    cells = {}
    label = label or System.Label
    for coord, system in self.systems.items():
      text = label(system)
      if coord == origin:
        text = '(%s)' % text
      elif coord in highlight:
        text = '[%s]' % text
      cells[(coord.q, 2 * coord.r + coord.q)] = text
    qs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    lines = []
    for y in range(min(ys), max(ys) + 1):
      line = ''.join(cells.get((x, y), '').center(width)
                     for x in range(min(qs), max(qs) + 1))
      lines.append(line.rstrip())
    return '\n'.join(lines) + '\n'
