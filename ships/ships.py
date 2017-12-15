#!/usr/bin/python
# Ship simulator, updated for TW4.

from __future__ import print_function

import pprint
import random

import dice

class CombatUnit(object):
  def __init__(self, edition = None):
    self.damage = 0
    self.movement = 0
    self.production_cost = 0
    if edition == None or edition == 4:
      self.edition = 4
    else:
      self.edition = 3

class GroundUnit(CombatUnit):
  pass

class SpaceVehicle(CombatUnit):
  def __init__(self, edition = None):
    super(SpaceVehicle, self).__init__(edition)
    self.capacity_limit = 0

  def GenerateHits(self):
    pass

  def ReceiveHits(self, amount):
    """Receive an amount of points of damage.

    Args:
      amount: Integer number.
    Returns:
      integer of number of hits left.
    """
    print ("NOTE: ship destroyed (%s)" % (self.__class__.__name__))
    return 0

  def TravelTo(self):
    pass

  def IsDamaged(self):
    return (self.damage > 0)

  def CanHandleDamage(self):
    return 1

  def WhereCanITravelTo(self):
    pass

  def ProductionSlotsTaken(self):
    pass

  def CanCarryGroundForces(self):
    return False

  def CanCarryPDSes(self):
    return False

  def CanCarryFighters(self):
    return False

  def CanGenerateAntiFighterBarrage(self):
    return False

  def CanSupportFighters(self):
    return False

  def ProvidePlanetaryShield(self):
    return False

  def AddToCargo(self, thing):
    if len(self.cargo) < self.capacity_limit:
      self.cargo.append(thing)
      return True
    else:
      print ("NOTE: cargo limit of %s exceeded", self.capacity_limit)
      return False

  def RemoveFromCargo(self):
    thing = pop(self.cargo)
    return thing

class Carrier(SpaceVehicle):
  def __init__(self, edition = None):
    super(Carrier, self).__init__(edition)
    self.movement = 1
    self.max_produceable = 4
    self.production_cost = 3
    if self.edition == None or self.edition == 4:
      self.capacity_limit = 4
    else:
      self.capacity_limit = 6
    self.cargo = []

  def CanCarryFighters(self):
    return True

  def CanCarryPDSes(self):
    return True

  def CanCarryGroundForces(self):
    return True

  def UpgradeCapacity(self):
    self.capacity_limit = 6

  def GenerateHits(self):
    return dice.Dice.RollWithTarget(9, 1)

class Cruiser(SpaceVehicle):
  def __init__(self, edition = 4):
    super(Cruiser, self).__init__(edition)
    self.movement = 2
    self.max_produceable = 8
    self.production_cost = 2

  def GenerateHits(self):
    return dice.Dice.RollWithTarget(7, 1)

class Destroyer(SpaceVehicle):
  def __init__(self, edition = 4):
    super(Destroyer, self).__init__(edition)
    self.movement = 2
    self.max_produceable = 8
    self.production_cost = 1

  def GenerateHits(self):
    return dice.Dice.RollWithTarget(9, 1)

  def CanGenerateAntiFighterBarrage(self):
    return True

  def GenerateAntiFighterBarrage(self):
    return Dice.RollWithTarget(9, 2)

class Dreadnought(SpaceVehicle):
  def __init__(self, edition = 4):
    super(Dreadnought, self).__init__(edition)
    self.movement = 2
    self.production_cost = 4 if self.edition == 4 else 5
    self.capacity_limit = 1

  def GenerateHits(self):
    return Dice.RollWithTarget(5, 1)

  def ReceiveHits(self, amount):
    amount_left = 2 - self.damage - amount
    if amount_left <= 0:
      print ("NOTE: ship destroyed (Dreadnought)")
      return 0
    elif amount == 1:
      self.damage = 1
      return 1
    elif amount == 0:
      return 2

  def CanHandleDamage(self):
    return 2

class Fighter(SpaceVehicle):
  def __init__(self, edition = 4):
    super(Fighter, self).__init__(edition)
    self.max_produceable = 10
    self.production_cost = 0.5

  def GenerateHits(self):
    return dice.Dice.RollWithTarget(9, 1)

class Flagship(SpaceVehicle):
  def __init__(self, edition = 4):
    super(Fighter, self).__init__(edition)
    self.max_produceable = 1
    self.production_cost = 5

  def GenerateHits(self):
    return dice.Dice.RollWithTarget(9, 1)

class Infantry(CombatUnit):
  pass

class PDS(SpaceVehicle):
  def __init__(self, edition = 4):
    super(PDS, self).__init__(edition)
    self.max_produceable = 6
    self.production_cost = 2

  def GenerateHits(self):
    return dice.Dice.RollWithTarget(6, 1)

  def ProvidePlanetaryShield(self):
    return True

class SpaceDock(SpaceVehicle):
  pass

class WarSun(SpaceVehicle):
  def __init__(self, edition = 4):
    super(WarSun, self).__init__(edition)
    self.movement = 2
    self.max_produceable = 2
    self.production_cost = 12
    self.cargo = []

  def GenerateHits(self):
    return dice.Dice.RollWithTarget(3, 3)

  def ReceiveHits(self, amount):
    amount_left = 2 - self.damage - amount
    if amount_left <= 0:
      print ("NOTE: ship destroyed (WarSun)")
      return 0
    elif amount == 1:
      self.damage = 1
      return 1
    elif amount == 0:
      return 2

  def CanHandleDamage(self):
    return 2

if __name__ == '__main__':
  pass
