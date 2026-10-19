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
]


class Agent(object):
    """A player's decision-maker. Subclasses override the choices they care about."""

    def AssignHits(self, units, hits):
        """Choose which of our ships take `hits` hits.

        Args:
          units: our ships in the combat (a list of Unit).
          hits: the number of hits to assign. The engine has already capped
            this at the total damage our ships can absorb.
        Returns:
          a list of Units, one entry per hit. A unit with Sustain Damage that
          appears once is damaged; appearing twice destroys it.
        """
        raise NotImplementedError

    def DeclareRetreat(self, own_units, enemy_units, round_number):
        """Return True to announce a retreat this combat round."""
        return False


class GreedyAgent(Agent):
    """Assigns hits to lose as little as possible; never retreats."""

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
