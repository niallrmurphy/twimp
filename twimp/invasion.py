#!/usr/bin/env python3
# Invasion, the step of a tactical action after space combat, following
# the TI4 rules:
#   1. Bombardment: units with Bombardment fire at planets holding other
#      players' ground forces, unless a Planetary Shield protects them.
#   2. Commit ground forces: land ground forces from space onto planets.
#   3. Space cannon defense: units with Space Cannon on a planet fire at the
#      ground forces committed to it.
#   4. Ground combat on each planet with ground forces of both sides.
#   5. Establish control: the active player gains each planet they hold
#      ground forces on; other players' structures there are destroyed.
#
# There is no board yet, so the caller passes the active player's ships and
# ground forces in the system's space area, and the system's planets.

import collections
import dataclasses
from typing import Any, List, Optional

from twimp import agents as agents_lib
from twimp import combat
from twimp import dice as dice_lib
from twimp.units import UnitType


class IllegalChoice(Exception):
    pass


@dataclasses.dataclass
class PlanetReport(object):
    """What happened on one planet during an invasion."""
    planet: Any
    bombardment_hits: int = 0
    bombardment_losses: List = dataclasses.field(default_factory=list)
    committed: List = dataclasses.field(default_factory=list)
    space_cannon_hits: int = 0
    space_cannon_losses: List = dataclasses.field(default_factory=list)
    ground_combat: Optional[combat.CombatResult] = None
    gained_control: bool = False
    structures_destroyed: List = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class InvasionResult(object):
    reports: List[PlanetReport]
    # Ground forces the active player left in space.
    ground_forces_in_space: List

    def ReportFor(self, planet):
        for report in self.reports:
            if report.planet is planet:
                return report
        raise KeyError(planet)


class Invasion(object):
    """One invasion by the active player. Call Resolve() to run every step."""

    def __init__(self, active_player, ships, ground_forces, planets,
                 agents=None, dice=None, listener=None):
        """
        Args:
          active_player: the invading player.
          ships: the active player's ships in the system.
          ground_forces: the active player's ground forces in the space area.
          planets: the system's planets (twimp.board.Planet).
          agents: {player: Agent}; any player not listed uses GreedyAgent.
          dice: a twimp.dice.Dice.
          listener: passed to each ground combat (see combat._Combat), with
            planet=, attacker= and defender= added.
        """
        for unit in ground_forces:
            if not unit.IsGroundForce():
                raise ValueError("Not a ground force: %r" % unit)
        self.active_player = active_player
        self.ships = list(ships)
        self.ground_forces = list(ground_forces)
        self.planets = list(planets)
        self.agents = agents or {}
        self.dice = dice if dice is not None else dice_lib.Dice()
        self.listener = listener
        self.reports = [PlanetReport(p) for p in self.planets]

    def _Agent(self, player):
        return self.agents.setdefault(player, agents_lib.GreedyAgent())

    def _Report(self, planet):
        return self.reports[self.planets.index(planet)]

    def Resolve(self):
        self._Bombardment()
        self._CommitGroundForces()
        self._SpaceCannonDefense()
        self._GroundCombat()
        self._EstablishControl()
        return InvasionResult(reports=self.reports,
                              ground_forces_in_space=self.ground_forces)

    # Step 1.
    def IsShielded(self, planet):
        """Planetary Shield protects a planet from bombardment, unless the
        active player has a war sun in the system."""
        if any(s.unit_type == UnitType.WARSUN for s in self.ships):
            return False
        return any(u.ProvidePlanetaryShield()
                   for player in planet.OtherPlayers(self.active_player)
                   for u in planet.UnitsOf(player))

    def BombardablePlanets(self):
        return [p for p in self.planets
                if self._Defender(p) is not None and not self.IsShielded(p)]

    def _Defender(self, planet):
        """The other player with ground forces on a planet, if any. We assume
        at most one: two other players can't share a planet."""
        for player in planet.OtherPlayers(self.active_player):
            if planet.GroundForces(player):
                return player
        return None

    def _Bombardment(self):
        bombarders = [s for s in self.ships if s.stats.bombardment is not None]
        allowed = self.BombardablePlanets()
        if not bombarders or not allowed:
            return
        choices = self._Agent(self.active_player).ChooseBombardment(
            self.active_player, list(bombarders), list(allowed))
        used = set()
        hits = collections.OrderedDict()
        for unit, planet in choices:
            if all(unit is not b for b in bombarders) or id(unit) in used:
                raise IllegalChoice("%r can't bombard (again)" % unit)
            if all(planet is not p for p in allowed):
                raise IllegalChoice("%r can't be bombarded" % planet)
            used.add(id(unit))
            hits[planet] = hits.get(planet, 0) + unit.GenerateBombardment(self.dice)
        for planet, planet_hits in hits.items():
            report = self._Report(planet)
            report.bombardment_hits = planet_hits
            report.bombardment_losses = self._HitGroundForces(
                planet, self._Defender(planet),
                planet.GroundForces(self._Defender(planet)), planet_hits)

    def _HitGroundForces(self, planet, owner, targets, hits):
        """The owner assigns hits among targets on a planet; losses are removed."""
        destroyed = combat.AssignAndApplyHits(list(targets), self._Agent(owner), hits)
        planet.RemoveUnits(owner, destroyed)
        return destroyed

    # Step 2.
    def _CommitGroundForces(self):
        if not self.ground_forces:
            return
        choices = self._Agent(self.active_player).CommitGroundForces(
            self.active_player, list(self.ground_forces), list(self.planets))
        used = set()
        for planet, units in choices.items():
            if all(planet is not p for p in self.planets):
                raise IllegalChoice("%r is not in this system" % planet)
            for unit in units:
                if all(unit is not g for g in self.ground_forces) or id(unit) in used:
                    raise IllegalChoice("%r can't be committed (again)" % unit)
                used.add(id(unit))
        for planet, units in choices.items():
            for unit in units:
                planet.AddUnit(self.active_player, unit)
                self._Report(planet).committed.append(unit)
        self.ground_forces = [g for g in self.ground_forces if id(g) not in used]

    # Step 3.
    def _SpaceCannonDefense(self):
        for planet in self.planets:
            report = self._Report(planet)
            if not report.committed:
                continue
            cannons = [u for player in planet.OtherPlayers(self.active_player)
                       for u in planet.UnitsOf(player)
                       if u.stats.space_cannon is not None]
            report.space_cannon_hits = sum(u.GenerateSpaceCannon(self.dice)
                                           for u in cannons)
            report.space_cannon_losses = self._HitGroundForces(
                planet, self.active_player, report.committed,
                report.space_cannon_hits)

    # Step 4.
    def _GroundCombat(self):
        for planet in self.planets:
            defender = self._Defender(planet)
            if defender is None or not planet.GroundForces(self.active_player):
                continue
            listener = None
            if self.listener:
                def listener(event, planet=planet, defender=defender, **details):
                    self.listener(event, planet=planet.name, attacker=self.active_player,
                                  defender=defender, **details)
            result = combat.GroundCombat(
                planet.GroundForces(self.active_player),
                planet.GroundForces(defender),
                attacker_agent=self._Agent(self.active_player),
                defender_agent=self._Agent(defender),
                dice=self.dice, listener=listener).Resolve()
            for round_report in result.rounds:
                planet.RemoveUnits(self.active_player, round_report.attacker_losses)
                planet.RemoveUnits(defender, round_report.defender_losses)
            self._Report(planet).ground_combat = result

    # Step 5.
    def _EstablishControl(self):
        for planet in self.planets:
            if not planet.GroundForces(self.active_player):
                continue
            report = self._Report(planet)
            if planet.controller != self.active_player:
                planet.GainControl(self.active_player)
                report.gained_control = True
            for player in planet.OtherPlayers(self.active_player):
                structures = planet.Structures(player)
                planet.RemoveUnits(player, structures)
                report.structures_destroyed += structures
