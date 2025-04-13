#!/usr/bin/env python3
# Ship simulator, updated for TW4.

from __future__ import print_function

import pprint
import random
import traceback

import ships


class Fleet(object):
    def __init__(self,
                 player_1_fleet,
                 player_2_fleet,
                 verbosity=False,
                 budget=None):
        if player_1_fleet is None:
            self.player_1_fleet = {}
        else:
            self.player_1_fleet = self.InstantiateShipObjects(player_1_fleet)
        if player_2_fleet is None:
            self.player_2_fleet = {}
        else:
            self.player_2_fleet = self.InstantiateShipObjects(player_2_fleet)
        self.verbosity = verbosity
        if budget is not None:
            self.budget = budget
        else:
            self.budget = 0

    def InstantiateShipObjects(self, fleet_obj):
        new_fleet = {}
        for ship_name in fleet_obj:
            try:
                new_ship_class = getattr(ships, ship_name)
                for i in range(fleet_obj[ship_name]):
                    ship = new_ship_class()
                    new_fleet.setdefault(ship_name, []).append(ship)
            except Exception as e:
                traceback.print_exc()
                print(e)
                print ("NOTE: ship creation failed - does %s exist?" % shiptype)
        return new_fleet

    def CountShipsOfType(self, ship_type):
        first = 0
        second = 0
        for k, v in self.player_1_fleet.items():
            if k == ship_type: first = len(v)
        for k, v in self.player_2_fleet.items():
            if k == ship_type: second = len(v)
        return (first, second)

    def InstantiateShipObjectsFromEnum(self, fleet_obj):
        pass

    def AddShipToFleet(self, ship_name, player_fleet=None, ignore_dock=True):
        """Add a ship to a fleet, observing all corner cases."""
        # Have to add to player 1 or player 2 fleet (as specified by player_fleet).
        #print("0")
        if player_fleet == None or player_fleet > 2: return False
        # Fleet has to have a space dock to build.
        if self.CountShipsOfType('SpaceDock') == 0 and ship_name != 'SpaceDock' and ignore_dock == False:
            return False
        #print("1")
        try:
            new_ship_class = getattr(ships, ship_name)
            ship = new_ship_class()
            if ship.production_cost > self.budget:
                return False
            #print ("2")
            if self.CountShipsOfType(ship_name)[player_fleet - 1] >= ship.max_produceable:
                return False
            #print ("3")
            new_ship_class = getattr(ships, ship_name)
            ship = new_ship_class()
            if player_fleet == 0 or player_fleet == 1:
                self.player_1_fleet.setdefault(ship_name, []).append(ship)
            elif player_fleet == 2:
                self.player_2_fleet.setdefault(ship_name, []).append(ship)
            #print ("4")
        except Exception as e:
                traceback.print_exc()
                print(e)
                print ("NOTE: ship creation failed - does %s exist?" % ship_name)
        #print("5")
        return True

    def AttackRound(self):
        """'Simultaneously' calculate fleet 1 and fleet 2 hits."""
        fleet_1_total_hits = 0
        fleet_2_total_hits = 0
        for shiptype in self.player_1_fleet:
            for ship in self.player_1_fleet[shiptype]:
                fleet_1_total_hits += ship.GenerateHits()
        if self.verbosity: print ("F1TH %s" % fleet_1_total_hits)
        for shiptype in self.player_2_fleet:
            for ship in self.player_2_fleet[shiptype]:
                fleet_2_total_hits += ship.GenerateHits()
        if self.verbosity: print ("F2TH %s" % fleet_2_total_hits)
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
            if self.verbosity: print ("Note: Wipeout for this fleet")
            return {}
        # 2. Now run down the damage clock.
        damage_distributed = 0
        ship_type_array = ['Fighter', 'Dreadnought', 'WarSun', 'Destroyer',
                            'Cruiser', 'Dreadnought', 'WarSun']
        for entity in ship_type_array:
            if fleet.get(entity):
                entity_amount = len(fleet.get(entity))
                damage_distributed = ApplyDamageRemovingShips(damage_distributed,
                                                              fleet, entity,
                                                              target_points)
                if damage_distributed == target_points:
                    return fleet
        return fleet

"""@staticmethod"""
def CalculateTotalDamageCapacity(fleet_obj):
    total_damage_capacity = 0
    for shiptype in fleet_obj:
        for ship in fleet_obj[shiptype]:
            total_damage_capacity += ship.CanHandleDamage()
    return total_damage_capacity

def ApplyDamageRemovingShips(damage_distributed, fleet, shiptype, points):
    if damage_distributed == points:
        print ("ApplyDamageRemovingShips: already at target points")
        return damage_distributed
    # The case where we haven't.
    to_remove = []
    for i, ship in enumerate(fleet[shiptype]):
        if points == 0:
            break
        if ship.ReceiveHits(1) == 0:
            to_remove.append(i)
            damage_distributed += 1
            points -= 1
    for i in reversed(to_remove):
        del fleet[shiptype][i]
    return damage_distributed

if __name__ == '__main__':
  pass
