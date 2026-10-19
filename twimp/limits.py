#!/usr/bin/env python3
# Unit limits within a system, following the TI4 rules:
#
# - Capacity: a player's fighters and ground forces in a system's space area
#   can't exceed the total capacity of their ships there. Up to 3 fighters
#   per space dock the player has in the system don't count. During combat
#   the limit can be exceeded; the excess is destroyed at the end of combat.
# - Fleet pool: a player can't have more non-fighter ships in a system than
#   command tokens in their fleet pool. Excess ships are removed.
#
# These functions measure and fix excess; the tactical action (stage 5)
# decides when to call them.

from twimp import agents as agents_lib
from twimp.units import UnitType

FIGHTERS_FREE_PER_SPACE_DOCK = 3


def Capacity(system, player):
    return sum(u.capacity_limit for u in system.ShipsOf(player))


def _SpaceDocks(system, player):
    return sum(1 for planet in system.planets for u in planet.UnitsOf(player)
               if u.unit_type == UnitType.SPACEDOCK)


def CarriedUnits(system, player):
    """Fighters and ground forces in the space area: the units that need capacity."""
    return [u for u in system.UnitsInSpace(player)
            if u.unit_type == UnitType.FIGHTER or u.IsGroundForce()]


def CapacityExcess(system, player):
    units = system.UnitsInSpace(player)
    fighters = sum(1 for u in units if u.unit_type == UnitType.FIGHTER)
    ground = sum(1 for u in units if u.IsGroundForce())
    free = FIGHTERS_FREE_PER_SPACE_DOCK * _SpaceDocks(system, player)
    return max(0, max(0, fighters - free) + ground - Capacity(system, player))


def FleetPoolShips(system, player):
    """Ships that count against the fleet pool: every ship except fighters."""
    return [u for u in system.ShipsOf(player) if u.unit_type != UnitType.FIGHTER]


def FleetPoolExcess(system, player, fleet_tokens):
    return max(0, len(FleetPoolShips(system, player)) - fleet_tokens)


def _Remove(state, system, player, candidates, count, agent, kind):
    chosen = agent.ChooseUnitsToRemove(list(candidates), count)
    if len(chosen) != count or any(all(c is not u for u in candidates) for c in chosen) \
            or len({id(c) for c in chosen}) != count:
        raise ValueError("Agent must choose %d distinct units from those offered" % count)
    system.space[player] = [u for u in system.UnitsInSpace(player)
                            if all(u is not c for c in chosen)]
    state.Log(kind, system=system.tile_id, player=player,
              units=[u.unit_type.name for u in chosen])
    return chosen


def EnforceCapacity(state, coord, player, agent=None):
    """Destroy fighters and ground forces beyond capacity. Returns them."""
    system = state.board.SystemAt(coord)
    excess = CapacityExcess(system, player)
    if not excess:
        return []
    return _Remove(state, system, player, CarriedUnits(system, player), excess,
                   agent or agents_lib.GreedyAgent(), 'capacity_exceeded')


def EnforceFleetPool(state, coord, player, agent=None):
    """Remove non-fighter ships beyond the fleet pool. Returns them."""
    system = state.board.SystemAt(coord)
    excess = FleetPoolExcess(system, player, state.Player(player).fleet_tokens)
    if not excess:
        return []
    return _Remove(state, system, player, FleetPoolShips(system, player), excess,
                   agent or agents_lib.GreedyAgent(), 'fleet_pool_exceeded')
