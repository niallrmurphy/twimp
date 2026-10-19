#!/usr/bin/env python3

class CannotPerformException(Exception):
  pass

class PermanentFeature(object):
  def isPermanent(self):
    return True

  def isTemporary(self):
    return False

class TemporaryFeature(object):
  def isPermanent(self):
    return False

  def isTemporary(self):
    return True

class Hex(object):
  """A board hex, which may contain permanent or temporary features."""
  def __init__(self,
               wormholes,
               planets,
               trade_stations
               ):
    self.wormholes = wormholes
    self.planets = planets
    self.trade_stations = trade_stations

  def Contains(self):
    return {"wormholes": self.wormholes,
            "planets": self.planets,
            "trade_stations": self.trade_stations}

  def _ContainsPermanent(self):
    """Return a list of objects that are permanent: e.g. planets, wormholes."""
    ret_list = []
    for item in self.planets:
      if item.isPermanent():
        ret_list.append(item)
    return ret_list

  def _ContainsTemporary(self):
    """Return a list of objects that are 'just passing through'."""
    ret_list = []
    for item in self.planets:
      if item.isTemporary():
        ret_list.append(item)
    return ret_list

  def AddEntity(self, entity):
    """Add an entity to the hex; temporary, like a ship, or permanent."""
    pass 

  def AddPlanet(self, planet):
    """Only add a planet to the hex."""
    self.planets.append(planet)

  def ConnectTo(self, hex, direction):
    """Connect this hex to another one in a particular direction, supplied."""
    # Directions can of course be via wormholes.
    pass

  def CanConnectTo(self):
    """Return a list of the other hexes does this hex connect to?"""
    pass

  def CanPassThrough(self, fleet):
    """Given a fleet, can it pass through this hex"""
    pass


class Nebula(Hex):
  pass


class Supernova(Hex):
  pass


class AsteroidField(Hex):
  pass


class IonStorm(Hex):
  pass


class Planet(PermanentFeature):
  """A TI4 planet. We won't bother with accessors/mutators for most of this."""
  def __init__(self,
               name,
               resources,
               influence):
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


class Board(object):
  def __init__(self):
    pass

  def GenerateRandom(self):
    pass

  def UsePreGeneratedBoard(self):
    pass

  def Display(self):
    pass

  def AddHexAtPosition(self):
    pass

