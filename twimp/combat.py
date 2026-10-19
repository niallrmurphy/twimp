#!/usr/bin/env python3
# Combat between two players, following the TI4 rules.
#
# Space combat: anti-fighter barrage, announce retreats, roll, assign hits,
# retreat, and repeat until one or both sides have no ships.
# Ground combat: roll, assign hits, and repeat until one or both sides have
# no ground forces. There is no retreat from ground combat.

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
    def __init__(self, name, units, agent, can_retreat=False):
        self.name = name
        self.units = list(units)
        self.agent = agent
        self.can_retreat = can_retreat

    def HasUnits(self):
        return bool(self.units)


def TotalDamageCapacity(units):
    """Total hits a list of units can absorb, including Sustain Damage."""
    return sum(u.CanHandleDamage() for u in units)


def ApplyAssignment(units, assignment, hits):
    """Validate and apply a hit assignment to a list of units, in place.

    Args:
      units: the units taking the hits; destroyed units are removed.
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


class _Combat(object):
    """The round loop shared by space and ground combat.

    A listener, if given, is called as listener(event, attacker_units=,
    defender_units=, ...) when the combat starts ('start'), once each round's
    dice are rolled ('rolled', with report=), after each round ('round', with
    report=), and when it ends ('end', with result=), so people can follow
    along.
    """

    def __init__(self, attacker, defender, dice, listener=None):
        self.attacker = attacker
        self.defender = defender
        self.dice = dice if dice is not None else dice_lib.Dice()
        self.rounds = []
        self.listener = listener

    def _Emit(self, event, **details):
        if self.listener:
            self.listener(event, attacker_units=list(self.attacker.units),
                          defender_units=list(self.defender.units), **details)

    def _BothSidesRemain(self):
        return self.attacker.HasUnits() and self.defender.HasUnits()

    def Resolve(self):
        retreated = None
        round_number = 0
        self._Emit('start')
        while self._BothSidesRemain():
            round_number += 1
            if round_number > MAX_ROUNDS:
                raise RuntimeError("Combat did not end after %d rounds" % MAX_ROUNDS)
            report = RoundReport(round_number)
            self.rounds.append(report)
            retreated = self._Round(report)
            self._Emit('round', report=report)
            if retreated is not None:
                break
        result = CombatResult(winner=self._Winner(retreated),
                              retreated=retreated,
                              attacker_units=self.attacker.units,
                              defender_units=self.defender.units,
                              rounds=self.rounds)
        self._Emit('end', result=result)
        return result

    def _Round(self, report):
        """Fight one round; return the name of a side that retreated, if any."""
        self._RollAndAssign(report)
        return None

    def _Winner(self, retreated):
        if retreated == ATTACKER:
            return DEFENDER
        if retreated == DEFENDER:
            return ATTACKER
        if self.attacker.HasUnits():
            return ATTACKER
        if self.defender.HasUnits():
            return DEFENDER
        return None

    def _RollAndAssign(self, report):
        report.attacker_hits = self._Roll(self.attacker)
        report.defender_hits = self._Roll(self.defender)
        # Let people see the dice before anyone has to assign hits.
        self._Emit('rolled', report=report)
        report.defender_losses += self._AssignHits(self.defender, report.attacker_hits)
        report.attacker_losses += self._AssignHits(self.attacker, report.defender_hits)

    def _Roll(self, side):
        return sum(u.GenerateHits(self.dice) for u in side.units)

    def _AssignHits(self, side, hits):
        return AssignAndApplyHits(side.units, side.agent, hits)


def AssignAndApplyHits(units, agent, hits):
    """Have an agent assign hits to its units (capped at what they can
    absorb), then apply them. Returns the destroyed units."""
    hits = min(hits, TotalDamageCapacity(units))
    if hits == 0:
        return []
    assignment = agent.AssignHits(list(units), hits)
    return ApplyAssignment(units, assignment, hits)


class SpaceCombat(_Combat):
    """One space combat. Call Resolve() to fight it to the end."""

    def __init__(self, attacker_units, defender_units,
                 attacker_agent=None, defender_agent=None, dice=None,
                 attacker_can_retreat=True, defender_can_retreat=True, listener=None):
        for unit in list(attacker_units) + list(defender_units):
            if not unit.IsShip():
                raise ValueError("Only ships take part in space combat: %r" % unit)
        # Whether a retreat is possible depends on the board (an adjacent
        # system without enemy ships), so for now the caller says.
        super(SpaceCombat, self).__init__(
            _Side(ATTACKER, attacker_units,
                  attacker_agent or agents_lib.GreedyAgent(),
                  attacker_can_retreat),
            _Side(DEFENDER, defender_units,
                  defender_agent or agents_lib.GreedyAgent(),
                  defender_can_retreat),
            dice, listener)

    def _Round(self, report):
        if report.round_number == 1:
            self._AntiFighterBarrage(report)
            if not self._BothSidesRemain():
                return None
        retreating = self._AnnounceRetreat(report.round_number)
        self._RollAndAssign(report)
        # A retreat only happens if both sides still have ships.
        if retreating is not None and self._BothSidesRemain():
            report.retreat = retreating.name
            return retreating.name
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


class GroundCombat(_Combat):
    """Ground combat on one planet. The attacker is the active player.

    Works on copies of the unit lists; the caller removes the units in
    each round's losses from the planet.
    """

    def __init__(self, attacker_units, defender_units,
                 attacker_agent=None, defender_agent=None, dice=None, listener=None):
        for unit in list(attacker_units) + list(defender_units):
            if not unit.IsGroundForce():
                raise ValueError("Only ground forces take part in ground combat: %r" % unit)
        super(GroundCombat, self).__init__(
            _Side(ATTACKER, attacker_units,
                  attacker_agent or agents_lib.GreedyAgent()),
            _Side(DEFENDER, defender_units,
                  defender_agent or agents_lib.GreedyAgent()),
            dice, listener)
