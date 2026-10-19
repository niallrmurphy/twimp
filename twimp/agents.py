#!/usr/bin/env python3
# Player decision interface. The rules engine never makes a choice a player
# would make; it asks an Agent.

from twimp.units import UnitType


# Order in which GreedyAgent assigns hits: cheapest losses first, with every
# Sustain Damage used before any ship is actually lost.
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
    (UnitType.INFANTRY, False),
]


class Agent(object):
    """A player's decision-maker. Subclasses override the choices they care about."""

    def AssignHits(self, units, hits):
        """Choose which of our units take `hits` hits.

        Used for space combat (ships), and for ground combat, bombardment and
        space cannon defense (ground forces).

        Args:
          units: our units that can be hit (a list of Unit).
          hits: the number of hits to assign. The engine has already capped
            this at the total damage those units can absorb.
        Returns:
          a list of Units, one entry per hit. A unit with Sustain Damage that
          appears once is damaged; appearing twice destroys it.
        """
        raise NotImplementedError

    def DeclareRetreat(self, own_units, enemy_units, round_number):
        """Return True to announce a retreat this combat round."""
        return False

    def ChooseBombardment(self, player, units, planets):
        """Choose which planet each of our bombarding units targets.

        Args:
          player: us.
          units: our units in the system with Bombardment.
          planets: planets we may bombard (they hold other players' ground
            forces and aren't shielded).
        Returns:
          a list of (unit, planet) pairs; each unit at most once. Leaving a
          unit out means it doesn't bombard.
        """
        return []

    def CommitGroundForces(self, player, ground_forces, planets):
        """Choose which of our ground forces in space land on which planets.

        Returns:
          {planet: [ground forces]}; each unit at most once.
        """
        return {}


class GreedyAgent(Agent):
    """Assigns hits to lose as little as possible and never retreats.

    Its invasion choices are deliberately simple: bombard the planet with
    the most enemy ground forces, and land everything on the weakest-held
    planet we don't control (preferring higher resources plus influence).
    """

    def ChooseBombardment(self, player, units, planets):
        if not planets:
            return []
        target = max(planets, key=lambda p: sum(
            len(p.GroundForces(o)) for o in p.OtherPlayers(player)))
        return [(unit, target) for unit in units]

    def CommitGroundForces(self, player, ground_forces, planets):
        candidates = [p for p in planets if p.controller != player]
        if not ground_forces or not candidates:
            return {}
        target = min(candidates, key=lambda p: (
            sum(len(p.GroundForces(o)) for o in p.OtherPlayers(player)),
            -(p.resources + p.influence)))
        return {target: list(ground_forces)}

    def AssignHits(self, units, hits):
        assignment = []
        pending = {id(u): 0 for u in units}
        for unit_type, sustain_only in MINIMUM_DAMAGE_ORDER:
            for unit in units:
                if len(assignment) == hits:
                    return assignment
                if unit.unit_type != unit_type:
                    continue
                left = unit.CanHandleDamage() - pending[id(unit)]
                to_assign = 1 if sustain_only and left > 1 else 0
                if not sustain_only:
                    to_assign = min(left, hits - len(assignment))
                assignment.extend([unit] * to_assign)
                pending[id(unit)] += to_assign
        return assignment
