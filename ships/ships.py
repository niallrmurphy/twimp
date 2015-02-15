#!/usr/bin/python


import pprint
import random

class Dice(object):
 
  @staticmethod
  def RollWithTarget(target_number,
                     number_of_dice,
                     sides=10,
                     verbosity=False):
    target_exceeded = 0
    for x in range(0, number_of_dice):
      y = random.randint(1, sides)
      if verbosity:
        print "NOTE: rolled ", y
      if y >= target_number:
        if verbosity:
          print "(>= Target)"
        target_exceeded += 1
    return target_exceeded

class SpaceVehicle(object):
  def __init__(self):
    self.damage = 0
    self.movement = 0
    self.production_cost = 0

  def GenerateHits(self):
    pass

  def ReceiveHits(self, amount):
    """Receive an amount of points of damage.

    Args:
      amount: Integer number.
    Returns:
      integer of number of hits left.  
    """
    print "NOTE: ship destroyed (%s)" % (self.__class__.__name__)
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
    if len(self.cargo) <= 5:
      self.cargo.append(thing)
      return True
    else:
      print "NOTE: cargo limit of 6 exceeded"
      return False

  def RemoveFromCargo(self):
    thing = pop(self.cargo)
    return thing

class Carrier(SpaceVehicle):
  def __init__(self):
    super(Carrier, self).__init__()
    self.movement = 1
    self.conventionally_available = 4
    self.production_cost = 3
    self.cargo = []

  def CanCarryFighters(self):
    return True

  def CanCarryPDSes(self):
    return True

  def CanCarryGroundForces(self):
    return True

  def GenerateHits(self):
    return Dice.RollWithTarget(9, 1)

class Cruiser(SpaceVehicle):
  def __init__(self):
    super(Cruiser, self).__init__()
    self.movement = 2
    self.conventionally_available = 8
    self.production_cost = 2

  def GenerateHits(self):
    return Dice.RollWithTarget(7, 1)

class Destroyer(SpaceVehicle):
  def __init__(self):
    super(Destroyer, self).__init__()
    self.movement = 2
    self.conventionally_available = 8
    self.production_cost = 1

  def GenerateHits(self):
    return Dice.RollWithTarget(9, 1)

  def CanGenerateAntiFighterBarrage(self):
    return True

  def GenerateAntiFighterBarrage(self):
    return Dice.RollWithTarget(9, 2)

class Dreadnought(SpaceVehicle):
  def __init__(self):
    super(Dreadnought, self).__init__()
    self.movement = 2
    self.production_cost = 5

  def GenerateHits(self):
    return Dice.RollWithTarget(5, 1)

  def ReceiveHits(self, amount):
    amount_left = 2 - self.damage - amount
    if amount_left <= 0:
      print "NOTE: ship destroyed (Dreadnought)"
      return 0
    elif amount == 1:
      self.damage = 1
      return 1
    elif amount == 0:
      return 2  
         
  def CanHandleDamage(self):
    return 2

class Fighter(SpaceVehicle):
  def __init__(self):
    super(Fighter, self).__init__()
    self.conventionally_available = 10
    self.production_cost = 0.5

  def GenerateHits(self):
    return Dice.RollWithTarget(9, 1)

class PDS(SpaceVehicle):
  def __init__(self):
    super(PDS, self).__init__()
    self.conventionally_available = 6
    self.production_cost = 2

  def GenerateHits(self):
    return Dice.RollWithTarget(6, 1)

  def ProvidePlanetaryShield(self):
    return True

class SpaceDock(SpaceVehicle):
  pass

class WarSun(SpaceVehicle):
  def __init__(self):
    super(WarSun, self).__init__()
    self.movement = 2
    self.conventionally_available = 2
    self.production_cost = 12
    self.cargo = []

  def GenerateHits(self):
    return Dice.RollWithTarget(3, 3)

  def ReceiveHits(self, amount):
    amount_left = 2 - self.damage - amount
    if amount_left <= 0:
      print "NOTE: ship destroyed (WarSun)"
      return 0
    elif amount == 1:
      self.damage = 1
      return 1
    elif amount == 0:
      return 2  
     
  def CanHandleDamage(self):
    return 2

class Fleet(object):
 
  # player_1_fleet{'Cruiser': 3, 'Fighter': 7}
  def __init__(self,
               player_1_fleet,
               player_2_fleet):
    if player_1_fleet is None:
      self.player_1_fleet = {}
    else:
      self.player_1_fleet = self.InstantiateShipObjects(player_1_fleet)
    if player_2_fleet is None:
      self.player_2_fleet = {}
    else:
      self.player_2_fleet = self.InstantiateShipObjects(player_2_fleet)
 
  def InstantiateShipObjects(self, fleet):
    new_fleet = {}
    for shiptype in fleet:
      try:
        new_ship_class = globals()[shiptype]
        for i in range(fleet[shiptype]):
          ship = new_ship_class()
          new_fleet.setdefault(shiptype, []).append(ship)
      except:
        print ("NOTE: ship creation failed - does %s exist?" % shiptype)
    return new_fleet
   
  def AttackRound(self):
    fleet_1_total_hits = 0
    fleet_2_total_hits = 0
    for shiptype in self.player_1_fleet:
      for ship in self.player_1_fleet[shiptype]:
        fleet_1_total_hits += ship.GenerateHits()
    for shiptype in self.player_2_fleet:
      for ship in self.player_2_fleet[shiptype]:
        fleet_2_total_hits += ship.GenerateHits()
    return (fleet_1_total_hits, fleet_2_total_hits)
 
  def DistributeMinimumDamage(self, fleet, target_points):
    """Distribute assigned damage to a fleet, attempting to minimise the impact.
   
    Kill off fighters first, then apply dreadnought half-damage, then warsun
    half-damage, then destroyers, cruisers, and finally dreadnought and warsun
    full-damage.
   
    Args:
      fleet: a fleet in dict format (e.g. {'Destroyer': [<ships.Destroyer object]})
      target_points: the number of points of damage to distribute
    Returns:
      fleet: the now presumably sadly depleted fleet.
    """
    # 1. Check for wipeout.
    if target_points >= CalculateTotalDamageCapacity(fleet):
      print "Note: Wipeout for this fleet"
      return {}
    # 2. Now run down the damage clock.
    damage_distributed = 0
    # Fighters.
    if fleet.get('Fighter'):
      fighter_amount = len(fleet.get('Fighter'))
    else:
      fighter_amount = 0
    if fighter_amount > 0:
      print "FIGHTER AMOUNT > 0"
      damage_distributed = RemoveElems(damage_distributed, fleet, 'Fighter',
                                       target_points)
      if damage_distributed == target_points:
        return fleet
    # Dreadnoughts (first pass)      
    if fleet.get('Dreadnought'):
      dreadnought_amount = len(fleet.get('Dreadnought'))
    else:
      dreadnought_amount = 0
    if dreadnought_amount > 0:
      print "DREADNOUGHT HALF-HITS"
      damage_distributed = RemoveElems(damage_distributed, fleet, 'Dreadnought',
                                       target_points)
      if damage_distributed == target_points:
        return fleet
    # Warsun half-hits.
    if fleet.get('WarSun'):
      warsun_amount = len(fleet.get('WarSun'))
    else:
      warsun_amount = 0    
    if warsun_amount > 0:
      print "WARSUN HALF HITS"
      damage_distributed = RemoveElems(damage_distributed, fleet, 'WarSun',
                                       target_points)
      if damage_distributed == target_points:
        return fleet      
    # Destroyers.
    if fleet.get('Destroyer'):
      destroyer_amount = len(fleet.get('Destroyer'))
    else:
      destroyer_amount = 0
    if destroyer_amount > 0:
      print "DESTROYER AMOUNT > 0"
      damage_distributed = RemoveElems(damage_distributed, fleet, 'Destroyer',
                                       target_points)
      if damage_distributed == target_points:
        return fleet      
    # Cruisers      
    if fleet.get('Cruiser'):
      cruiser_amount = len(fleet.get('Cruiser'))
    else:
      cruiser_amount = 0
    if cruiser_amount > 0:
      print "CRUISER AMOUNT > 0"
      damage_distributed = RemoveElems(damage_distributed, fleet, 'Cruiser',
                                       target_points)
      if damage_distributed == target_points:
        return fleet
    # Come back to Dreadnought/WarSuns.
    if fleet.get('Dreadnought'):
      dreadnought_amount = len(fleet.get('Dreadnought'))
      if dreadnought_amount > 0:
        print "DREADNOUGHT FULL HITS"
        damage_distributed = RemoveElems(damage_distributed, fleet, 'Dreadnought',
                                         target_points)
        if damage_distributed == target_points:
          return fleet                                        
    if fleet.get('WarSun'):
      warsun_amount = len(fleet.get('WarSun'))
      if warsun_amount > 0:
        print "WARSUN FULL HITS"
        damage_distributed = RemoveElems(damage_distributed, fleet, 'WarSun',
                                         target_points)
    return fleet
     
def CalculateTotalDamageCapacity(fleet):
  total_damage_capacity = 0
  for shiptype in fleet:
    for ship in fleet[shiptype]:
      total_damage_capacity += ship.CanHandleDamage()
  return total_damage_capacity

def RemoveElems(damage_distributed, fleet, shiptype, points):
  """Apply hits to ships in fleets and remove them if necessary.
 
  damage_distributed: a running counter of how many points of damage
                      have been distributed
  fleet: the fleet object(s) in dict format
  shiptype: 'Fighter', 'Cruiser' etc
  points: total number of points of damage we're going to distribute over
          the fleet
  """
  # The case where we've already got to the target points.
  if damage_distributed == points:
    print "REMOVEELEMS: already at target points"
    return damage_distributed
  # The case where we haven't.
  to_remove = []
  for i, ship in enumerate(fleet[shiptype]):
    print "SHIP", ship
    print "SHIP DAMAGE", ship.damage
    if ship.ReceiveHits(1) == 0:
      to_remove.append(i)
    damage_distributed += 1
  for i in reversed(to_remove):
    del fleet[shiptype][i]
  return damage_distributed

if __name__ == '__main__':
  pass


