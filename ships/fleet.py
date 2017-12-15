#!/usr/bin/python
# Ship simulator, updated for TW4.

from __future__ import print_function

import pprint
import random
import traceback

import ships

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

  def InstantiateShipObjects(self, fleet_obj):
    new_fleet = {}
    for shiptype in fleet_obj:
      try:
        new_ship_class = getattr(ships, shiptype)
        for i in range(fleet_obj[shiptype]):
          ship = new_ship_class()
          new_fleet.setdefault(shiptype, []).append(ship)
      except Exception as e:
        traceback.print_exc()
        print(e)
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
      print ("Note: Wipeout for this fleet")
      return {}
    # 2. Now run down the damage clock.
    damage_distributed = 0
    # Fighters.
    if fleet.get('Fighter'):
      fighter_amount = len(fleet.get('Fighter'))
    else:
      fighter_amount = 0
    if fighter_amount > 0:
      print ("FIGHTER AMOUNT > 0")
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
      print ("DREADNOUGHT HALF-HITS")
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
      print ("WARSUN HALF HITS")
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
      print ("DESTROYER AMOUNT > 0")
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
      print ("CRUISER AMOUNT > 0")
      damage_distributed = RemoveElems(damage_distributed, fleet, 'Cruiser',
                                       target_points)
      if damage_distributed == target_points:
        return fleet
    # Come back to Dreadnought/WarSuns.
    if fleet.get('Dreadnought'):
      dreadnought_amount = len(fleet.get('Dreadnought'))
      if dreadnought_amount > 0:
        print ("DREADNOUGHT FULL HITS")
        damage_distributed = RemoveElems(damage_distributed, fleet, 'Dreadnought',
                                         target_points)
        if damage_distributed == target_points:
          return fleet
    if fleet.get('WarSun'):
      warsun_amount = len(fleet.get('WarSun'))
      if warsun_amount > 0:
        print ("WARSUN FULL HITS")
        damage_distributed = RemoveElems(damage_distributed, fleet, 'WarSun',
                                         target_points)
    return fleet

def CalculateTotalDamageCapacity(fleet_obj):
  total_damage_capacity = 0
  for shiptype in fleet_obj:
    for ship in fleet_obj[shiptype]:
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
    print ("REMOVEELEMS: already at target points")
    return damage_distributed
  # The case where we haven't.
  to_remove = []
  for i, ship in enumerate(fleet[shiptype]):
    print ("SHIP", ship)
    print ("SHIP DAMAGE", ship.damage)
    if ship.ReceiveHits(1) == 0:
      to_remove.append(i)
    damage_distributed += 1
  for i in reversed(to_remove):
    del fleet[shiptype][i]
  return damage_distributed

if __name__ == '__main__':
  pass
