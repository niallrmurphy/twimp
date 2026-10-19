#!/usr/bin/env python3
# Space combat between two players' ships in one system, following the
# TI4 rules: anti-fighter barrage, announce retreats, roll, assign hits,
# retreat, and repeat until one or both sides have no ships.

import collections
import dataclasses
from typing import List, Optional

from twimp import agents as agents_lib
from twimp import dice as dice_lib
from twimp.units import UnitType

ATTACKER = 'attacker'
DEFENDER = 'defender'

# Guard against a combat that never ends (e.g. only units that can't hit).
MAX_ROUNDS = 1000


class IllegalAssignment(Exception):
    pass


@dataclasses.dataclass
class RoundReport(object):
    """What happened in one combat round, for logs and tests."""
    round_number: int
    attacker_afb_hits: int = 0
    defender_afb_hits: int = 0
    attacker_hits: int = 0
    defender_hits: int = 0
    attacker_losses: List = dataclasses.field(default_factory=list)
    defender_losses: List = dataclasses.field(default_factory=list)
    retreat: Optional[str] = None


@dataclasses.dataclass
class CombatResult(object):
    winner: Optional[str]          # ATTACKER, DEFENDER, or None for a draw
    retreated: Optional[str]       # the side that retreated, if any
    attacker_units: List
    defender_units: List
    rounds: List[RoundReport]


class _Side(object):
    def __init__(self, name, units, agent, can_retreat):
        for unit in units:
            if not unit.IsShip():
                raise ValueError("Only ships take part in space combat: %r" % unit)
        self.name = name
        self.units = list(units)
        self.agent = agent
        self.can_retreat = can_retreat

    def HasShips(self):
        return bool(self.units)


def TotalDamageCapacity(units):
    """Total hits a list of ships can absorb, including Sustain Damage."""
    return sum(u.CanHandleDamage() for u in units if u.IsShip())


def ApplyAssignment(units, assignment, hits):
    """Validate and apply a hit assignment to a list of ships, in place.

    Args:
      units: the ships taking the hits; destroyed ships are removed.
      assignment: a list of Units, one per hit (see Agent.AssignHits).
      hits: the number of hits that had to be assigned.
    Returns:
      the list of destroyed units.
    """
    if len(assignment) != hits:
        raise IllegalAssignment("Assigned %d hits, needed %d" % (len(assignment), hits))
    counts = collections.Counter(id(u) for u in assignment)
    by_id = {id(u): u for u in units}
    destroyed = []
    for unit_id, count in counts.items():
        unit = by_id.get(unit_id)
        if unit is None:
            raise IllegalAssignment("Assigned a hit to a unit not in the combat")
        if count > unit.CanHandleDamage():
            raise IllegalAssignment("%r can't take %d hits" % (unit, count))
    for unit_id, count in counts.items():
        unit = by_id[unit_id]
        if unit.ReceiveHits(count) == 0:
            destroyed.append(unit)
    units[:] = [u for u in units if all(u is not d for d in destroyed)]
    return destroyed


class SpaceCombat(object):
    """One space combat. Call Resolve() to fight it to the end."""

    def __init__(self, attacker_units, defender_units,
                 attacker_agent=None, defender_agent=None, dice=None,
                 attacker_can_retreat=True, defender_can_retreat=True):
        # Whether a retreat is possible depends on the board (an adjacent
        # system without enemy ships), so for now the caller says.
        self.attacker = _Side(ATTACKER, attacker_units,
                              attacker_agent or agents_lib.GreedyAgent(),
                              attacker_can_retreat)
        self.defender = _Side(DEFENDER, defender_units,
                              defender_agent or agents_lib.GreedyAgent(),
                              defender_can_retreat)
        self.dice = dice if dice is not None else dice_lib.Dice()
        self.rounds = []

    def Resolve(self):
        retreated = None
        round_number = 0
        while self.attacker.HasShips() and self.defender.HasShips():
            round_number += 1
            if round_number > MAX_ROUNDS:
                raise RuntimeError("Combat did not end after %d rounds" % MAX_ROUNDS)
            report = RoundReport(round_number)
            self.rounds.append(report)
            if round_number == 1:
                self._AntiFighterBarrage(report)
                if not (self.attacker.HasShips() and self.defender.HasShips()):
                    break
            retreating = self._AnnounceRetreat(round_number)
            self._RollAndAssign(report)
            # A retreat only happens if both sides still have ships.
            if (retreating is not None and self.attacker.HasShips()
                    and self.defender.HasShips()):
                report.retreat = retreating.name
                retreated = retreating.name
                break
        return CombatResult(winner=self._Winner(retreated),
                            retreated=retreated,
                            attacker_units=self.attacker.units,
                            defender_units=self.defender.units,
                            rounds=self.rounds)

    def _Winner(self, retreated):
        if retreated == ATTACKER:
            return DEFENDER
        if retreated == DEFENDER:
            return ATTACKER
        if self.attacker.HasShips():
            return ATTACKER
        if self.defender.HasShips():
            return DEFENDER
        return None

    def _AntiFighterBarrage(self, report):
        """First round only: each side's AFB hits destroy the other's fighters."""
        report.attacker_afb_hits = self._RollAfb(self.attacker, self.defender)
        report.defender_afb_hits = self._RollAfb(self.defender, self.attacker)
        report.defender_losses += self._DestroyFighters(self.defender,
                                                        report.attacker_afb_hits)
        report.attacker_losses += self._DestroyFighters(self.attacker,
                                                        report.defender_afb_hits)

    def _RollAfb(self, side, enemy):
        # No point rolling (or consuming dice) if there are no fighters to hit.
        if not any(u.unit_type == UnitType.FIGHTER for u in enemy.units):
            return 0
        return sum(u.GenerateAntiFighterBarrage(self.dice) for u in side.units)

    def _DestroyFighters(self, side, hits):
        fighters = [u for u in side.units if u.unit_type == UnitType.FIGHTER]
        destroyed = fighters[:hits]
        side.units = [u for u in side.units if all(u is not d for d in destroyed)]
        return destroyed

    def _AnnounceRetreat(self, round_number):
        """The defender announces first; if it retreats, the attacker can't."""
        for side, enemy in ((self.defender, self.attacker),
                            (self.attacker, self.defender)):
            if side.can_retreat and side.agent.DeclareRetreat(
                    list(side.units), list(enemy.units), round_number):
                return side
        return None

    def _RollAndAssign(self, report):
        report.attacker_hits = self._Roll(self.attacker)
        report.defender_hits = self._Roll(self.defender)
        report.defender_losses += self._AssignHits(self.defender, report.attacker_hits)
        report.attacker_losses += self._AssignHits(self.attacker, report.defender_hits)

    def _Roll(self, side):
        return sum(u.GenerateHits(self.dice) for u in side.units)

    def _AssignHits(self, side, hits):
        hits = min(hits, TotalDamageCapacity(side.units))
        if hits == 0:
            return []
        assignment = side.agent.AssignHits(list(side.units), hits)
        return ApplyAssignment(side.units, assignment, hits)
