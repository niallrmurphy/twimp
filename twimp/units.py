#!/usr/bin/env python3
# Unit definitions for Twilight Imperium 4th edition (base game).

import dataclasses
import enum
from typing import Optional


class UnitType(enum.Enum):
    SPACEDOCK = 1
    PDS = 2
    FIGHTER = 3
    CARRIER = 4
    CRUISER = 5
    DESTROYER = 6
    DREADNOUGHT = 7
    WARSUN = 8
    FLAGSHIP = 9
    INFANTRY = 10


class Category(enum.Enum):
    SHIP = 1
    GROUND_FORCE = 2
    STRUCTURE = 3


@dataclasses.dataclass(frozen=True)
class Ability(object):
    """A dice-rolling unit ability, e.g. Anti-Fighter Barrage 9 (x2)."""
    value: int
    dice: int = 1


@dataclasses.dataclass(frozen=True)
class UnitStats(object):
    """The printed (unupgraded) stats of a unit, as on the 4e faction sheet.

    combat is None for units that don't take part in combat (PDS, space dock).
    cost buys units_per_cost units: fighters and infantry are 1 for 2.
    plastic_limit is None for fighters and infantry, which may use tokens
    once the plastic runs out.
    production is a flat value; for a space dock it is added to the
    resources of the planet it is on.
    """
    category: Category
    cost: Optional[int]
    combat: Optional[int] = None
    combat_dice: int = 1
    move: int = 0
    capacity: int = 0
    units_per_cost: int = 1
    sustain_damage: bool = False
    anti_fighter_barrage: Optional[Ability] = None
    bombardment: Optional[Ability] = None
    space_cannon: Optional[Ability] = None
    planetary_shield: bool = False
    production: Optional[int] = None
    plastic_limit: Optional[int] = None

    @property
    def unit_cost(self):
        """Cost of a single unit, e.g. 0.5 for a fighter."""
        if self.cost is None:
            return None
        return self.cost / self.units_per_cost


UNIT_STATS = {
    UnitType.CARRIER: UnitStats(
        category=Category.SHIP, cost=3, combat=9, move=1, capacity=4,
        plastic_limit=4),
    UnitType.CRUISER: UnitStats(
        category=Category.SHIP, cost=2, combat=7, move=2,
        plastic_limit=8),
    UnitType.DESTROYER: UnitStats(
        category=Category.SHIP, cost=1, combat=9, move=2,
        anti_fighter_barrage=Ability(9, 2), plastic_limit=8),
    UnitType.DREADNOUGHT: UnitStats(
        category=Category.SHIP, cost=4, combat=5, move=1, capacity=1,
        sustain_damage=True, bombardment=Ability(5), plastic_limit=5),
    UnitType.WARSUN: UnitStats(
        category=Category.SHIP, cost=12, combat=3, combat_dice=3, move=2,
        capacity=6, sustain_damage=True, bombardment=Ability(3, 3),
        plastic_limit=2),
    UnitType.FIGHTER: UnitStats(
        category=Category.SHIP, cost=1, units_per_cost=2, combat=9),
    # Flagships are faction-specific; this is a stand-in until factions
    # exist. Only cost, sustain damage and the limit of 1 are common to all.
    UnitType.FLAGSHIP: UnitStats(
        category=Category.SHIP, cost=8, combat=7, combat_dice=2, move=1,
        capacity=3, sustain_damage=True, plastic_limit=1),
    UnitType.INFANTRY: UnitStats(
        category=Category.GROUND_FORCE, cost=1, units_per_cost=2, combat=8),
    UnitType.PDS: UnitStats(
        category=Category.STRUCTURE, cost=None, space_cannon=Ability(6),
        planetary_shield=True, plastic_limit=6),
    UnitType.SPACEDOCK: UnitStats(
        category=Category.STRUCTURE, cost=None, production=2,
        plastic_limit=3),
}


class Unit(object):
    """A single unit on the board: a ship, ground force or structure."""
    def __init__(self, unit_type, verbosity=False):
        if not isinstance(unit_type, UnitType):
            raise ValueError("Not a UnitType: %r" % (unit_type,))
        self.unit_type = unit_type
        self.stats = UNIT_STATS[unit_type]
        self.damaged = False
        self.cargo = []
        self.verbosity = verbosity

    def __repr__(self):
        return "<Unit %s%s>" % (self.unit_type.name,
                                " (damaged)" if self.damaged else "")

    @property
    def movement(self):
        return self.stats.move

    @property
    def capacity_limit(self):
        return self.stats.capacity

    @property
    def production_cost(self):
        return self.stats.unit_cost

    @property
    def max_produceable(self):
        return self.stats.plastic_limit

    def IsShip(self):
        return self.stats.category == Category.SHIP

    def IsGroundForce(self):
        return self.stats.category == Category.GROUND_FORCE

    def IsStructure(self):
        return self.stats.category == Category.STRUCTURE

    def IsDamaged(self):
        return self.damaged

    def Repair(self):
        self.damaged = False

    def GenerateHits(self, dice):
        """Roll this unit's combat dice; return the number of hits."""
        if self.stats.combat is None:
            return 0
        return dice.RollWithTarget(self.stats.combat, self.stats.combat_dice)

    def _RollAbility(self, ability, dice):
        if ability is None:
            return 0
        return dice.RollWithTarget(ability.value, ability.dice)

    def GenerateAntiFighterBarrage(self, dice):
        return self._RollAbility(self.stats.anti_fighter_barrage, dice)

    def GenerateBombardment(self, dice):
        return self._RollAbility(self.stats.bombardment, dice)

    def GenerateSpaceCannon(self, dice):
        return self._RollAbility(self.stats.space_cannon, dice)

    def CanGenerateAntiFighterBarrage(self):
        return self.stats.anti_fighter_barrage is not None

    def ProvidePlanetaryShield(self):
        return self.stats.planetary_shield

    def CanHandleDamage(self):
        """How many more hits can this unit take before being destroyed?"""
        if self.stats.sustain_damage and not self.damaged:
            return 2
        return 1

    def ReceiveHits(self, amount):
        """Receive an amount of points of damage.

        Args:
          amount: Integer number.
        Returns:
          integer of number of hits this unit can still take; 0 means destroyed.
        """
        remaining = self.CanHandleDamage() - amount
        if remaining <= 0:
            if self.verbosity: print ("NOTE: unit destroyed (%s)" % self.unit_type.name)
            return 0
        if amount > 0:
            self.damaged = True
        return remaining

    def CanCarryFighters(self):
        return self.stats.capacity > 0

    def CanCarryGroundForces(self):
        return self.stats.capacity > 0

    def AddToCargo(self, thing):
        if len(self.cargo) < self.capacity_limit:
            self.cargo.append(thing)
            return True
        if self.verbosity: print ("NOTE: cargo limit of %s exceeded" % self.capacity_limit)
        return False

    def RemoveFromCargo(self):
        return self.cargo.pop()


if __name__ == '__main__':
    pass
