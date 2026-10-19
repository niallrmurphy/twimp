#!/usr/bin/env python3
# Which systems a ship can move to, following the TI4 movement rules:
#
# - Each move goes to an adjacent system: physically next to it, or through
#   a matching wormhole.
# - Ships can't move through a system containing another player's ships,
#   but can end their move there.
# - Supernova: ships can't move into or through it.
# - Asteroid field: ships can't move into or through it (unless the player
#   has Antimass Deflectors).
# - Nebula: ships can end their move in it but not move through it, and a
#   ship that starts its move in a nebula has a move value of 1.
# - Gravity rift: a ship gets +1 move for each gravity rift it moves out of,
#   and rolls a die each time it does; on 1-3 it is destroyed.
#
# A ship also can't move out of (or so through) a system containing its
# player's command token; the tactical action passes those as no_pass.

import dataclasses
from typing import Tuple

from twimp import board as board_lib

GRAVITY_RIFT_DESTROYS_ON = 3


@dataclasses.dataclass(frozen=True)
class Path(object):
    """A route a ship can take: the systems from start to destination."""
    systems: Tuple
    # How many times the route moves out of a gravity rift (each needs a roll).
    rifts_exited: int

    @property
    def destination(self):
        return self.systems[-1]

    def _Preference(self):
        # Safer routes first, then shorter ones.
        return (self.rifts_exited, len(self.systems))


def _CanEnter(system, can_pass_asteroids):
    if system.anomaly == board_lib.Anomaly.SUPERNOVA:
        return False
    if system.anomaly == board_lib.Anomaly.ASTEROID_FIELD and not can_pass_asteroids:
        return False
    return True


def _CanMoveThrough(system, player):
    if system.anomaly == board_lib.Anomaly.NEBULA:
        return False
    return not system.HasOtherPlayersShips(player)


def ReachableSystems(board, start, move, player, can_pass_asteroids=False,
                     no_pass=()):
    """Every system a ship with `move` starting at `start` can end its move in.

    no_pass: coordinates the ship may end in but not move through.

    Returns:
      {coordinates: Path}, using the route with the fewest gravity rift exits
      (then the shortest) for each destination. The start isn't included.
    """
    if board.SystemAt(start).anomaly == board_lib.Anomaly.NEBULA:
        move = min(move, 1)
    best = {}

    def Explore(path, budget, rifts):
        current = path[-1]
        rift_bonus = 1 if board.SystemAt(current).anomaly == board_lib.Anomaly.GRAVITY_RIFT else 0
        remaining = budget - 1 + rift_bonus
        if remaining < 0:
            return
        for neighbour in board.Adjacent(current):
            if neighbour in path:
                continue
            system = board.SystemAt(neighbour)
            if not _CanEnter(system, can_pass_asteroids):
                continue
            route = Path(tuple(path) + (neighbour,), rifts + rift_bonus)
            if (neighbour not in best
                    or route._Preference() < best[neighbour]._Preference()):
                best[neighbour] = route
            if _CanMoveThrough(system, player) and neighbour not in no_pass:
                Explore(route.systems, remaining, route.rifts_exited)

    if move > 0:
        Explore((start,), move, 0)
    best.pop(start, None)
    return best


def ReachableForUnit(board, start, unit, player, can_pass_asteroids=False):
    """Reachable systems for one unit. Units with no move value (fighters,
    ground forces, structures) can't move by themselves."""
    return ReachableSystems(board, start, unit.movement, player, can_pass_asteroids)


def SurvivesGravityRift(dice):
    """Roll for a ship moving out of a gravity rift: destroyed on 1-3."""
    return dice.Roll() > GRAVITY_RIFT_DESTROYS_ON
