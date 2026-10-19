#!/usr/bin/env python3
# Two-sided fleet simulator, for TI4.

from twimp import dice as dice_lib
from twimp.units import Unit, UnitType


# Order in which hits are assigned by DistributeMinimumDamage: cheapest losses
# first. Sustain Damage passes come before any ship is actually lost.
# Each entry is (unit type, sustain_only).
MINIMUM_DAMAGE_ORDER = [
    (UnitType.FIGHTER, False),
    (UnitType.DREADNOUGHT, True),
    (UnitType.WARSUN, True),
    (UnitType.FLAGSHIP, True),
    (UnitType.DESTROYER, False),
    (UnitType.CRUISER, False),
    (UnitType.CARRIER, False),
    (UnitType.DREADNOUGHT, False),
    (UnitType.FLAGSHIP, False),
    (UnitType.WARSUN, False),
]


class Fleet(object):
    """Two players' forces, keyed by UnitType: {UnitType: [Unit, ...]}."""
    def __init__(self,
                 player_1_fleet,
                 player_2_fleet,
                 verbosity=False,
                 budget=None,
                 dice=None):
        self.verbosity = verbosity
        self.player_1_fleet = self.InstantiateShipObjects(player_1_fleet or {})
        self.player_2_fleet = self.InstantiateShipObjects(player_2_fleet or {})
        self.budget = budget if budget is not None else 0
        self.dice = dice if dice is not None else dice_lib.Dice()

    def InstantiateShipObjects(self, fleet_obj):
        """Turn {UnitType: count} into {UnitType: [Unit, ...]}."""
        new_fleet = {}
        for unit_type, count in fleet_obj.items():
            for i in range(count):
                new_fleet.setdefault(unit_type, []).append(
                    Unit(unit_type, verbosity=self.verbosity))
        return new_fleet

    def _PlayerFleet(self, player_fleet):
        if player_fleet == 1:
            return self.player_1_fleet
        if player_fleet == 2:
            return self.player_2_fleet
        return None

    def CountShipsOfType(self, ship_type):
        return (len(self.player_1_fleet.get(ship_type, [])),
                len(self.player_2_fleet.get(ship_type, [])))

    def AddShipToFleet(self, ship_type, player_fleet=None, ignore_dock=True):
        """Build a unit for player 1 or 2, spending from the budget.

        Fails (returning False) for an unknown player, when there is no space
        dock (unless ignore_dock), when the unit costs more than the remaining
        budget, or when the player already has the unit's plastic limit.
        """
        fleet = self._PlayerFleet(player_fleet)
        if fleet is None:
            return False
        if (not ignore_dock and ship_type != UnitType.SPACEDOCK
                and not fleet.get(UnitType.SPACEDOCK)):
            return False
        ship = Unit(ship_type, verbosity=self.verbosity)
        cost = ship.production_cost or 0
        if cost > self.budget:
            return False
        limit = ship.max_produceable
        if limit is not None and len(fleet.get(ship_type, [])) >= limit:
            return False
        fleet.setdefault(ship_type, []).append(ship)
        self.budget -= cost
        return True

    def AttackRound(self):
        """'Simultaneously' calculate fleet 1 and fleet 2 hits."""
        fleet_1_total_hits = self._RollFleet(self.player_1_fleet)
        if self.verbosity: print ("F1TH %s" % fleet_1_total_hits)
        fleet_2_total_hits = self._RollFleet(self.player_2_fleet)
        if self.verbosity: print ("F2TH %s" % fleet_2_total_hits)
        return (fleet_1_total_hits, fleet_2_total_hits)

    def _RollFleet(self, fleet):
        hits = 0
        for ships in fleet.values():
            for ship in ships:
                if ship.IsShip():
                    hits += ship.GenerateHits(self.dice)
        return hits

    def DistributeMinimumDamage(self, fleet, target_points):
        """Distribute assigned damage to a fleet, attempting to minimise the impact.

        Kill off fighters first, then use Sustain Damage on dreadnoughts, war
        suns and flagships, then lose destroyers, cruisers, carriers, and
        finally dreadnoughts, flagships and war suns. Only ships take hits.

        Args:
        fleet: a fleet in dict format (e.g. {UnitType.DESTROYER: [<Unit>]}),
          modified in place.
        target_points: the number of points of damage to distribute
        Returns:
        fleet: the now presumably sadly depleted fleet.
        """
        # 1. Check for wipeout.
        if target_points >= CalculateTotalDamageCapacity(fleet):
            if self.verbosity: print ("Note: Wipeout for this fleet")
            for unit_type in [t for t, units in fleet.items()
                              if units and units[0].IsShip()]:
                del fleet[unit_type]
            return fleet
        # 2. Now run down the damage clock.
        remaining = target_points
        for unit_type, sustain_only in MINIMUM_DAMAGE_ORDER:
            if remaining == 0:
                break
            if fleet.get(unit_type):
                remaining -= ApplyHitsToType(fleet, unit_type, remaining,
                                             sustain_only)
        return fleet


def CalculateTotalDamageCapacity(fleet_obj):
    """Total hits the ships in a fleet can absorb, including Sustain Damage."""
    total_damage_capacity = 0
    for units in fleet_obj.values():
        for unit in units:
            if unit.IsShip():
                total_damage_capacity += unit.CanHandleDamage()
    return total_damage_capacity


def ApplyHitsToType(fleet, unit_type, hits, sustain_only=False):
    """Assign up to `hits` hits, one per unit, to units of one type.

    With sustain_only, only undamaged units with Sustain Damage are hit, and
    they are damaged rather than destroyed. Otherwise each hit destroys a unit.
    Destroyed units are removed from the fleet.

    Returns:
      the number of hits actually assigned.
    """
    assigned = 0
    survivors = []
    for unit in fleet[unit_type]:
        if assigned == hits:
            survivors.append(unit)
        elif sustain_only:
            if unit.CanHandleDamage() > 1:
                unit.ReceiveHits(1)
                assigned += 1
            survivors.append(unit)
        else:
            unit.ReceiveHits(unit.CanHandleDamage())
            assigned += 1
    fleet[unit_type] = survivors
    return assigned


if __name__ == '__main__':
    pass
