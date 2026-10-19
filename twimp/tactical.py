#!/usr/bin/env python3
# The tactical action: one player's turn of moving and fighting, following
# the TI4 rules.
#
#   1. Activation: place a tactic token in a system that doesn't already
#      hold one of your command tokens.
#   2. Movement: move ships into the active system, carrying fighters and
#      ground forces from the system each ship starts in. Then space cannon
#      offense: PDS in the active system fire, starting with the active
#      player, at other players' ships there.
#   3. Space combat, if another player has ships there. A side may retreat
#      to an adjacent system with no enemy ships that holds its units or a
#      planet it controls, placing a command token there from reinforcements.
#      Fighters and ground forces beyond capacity are destroyed after combat.
#   4. Invasion (see invasion.py). Ground forces can't land on Mecatol Rex
#      while the custodians token is on it.
#   5. Production: the active player's space docks in the system produce
#      up to their combined limit (planet resources + 2 each), paid by
#      exhausting planets and spending trade goods. A blockaded space dock
#      (enemy ships, none of ours) can't produce ships.
#
# Every choice comes from the players' Agents and is validated here.

import dataclasses
from typing import Any, Dict, List, Optional

from twimp import agents as agents_lib
from twimp import combat
from twimp import dice as dice_lib
from twimp import game as game_lib
from twimp import hexes
from twimp import invasion as invasion_lib
from twimp import limits
from twimp import movement
from twimp.units import Category, Unit, UnitType

MECATOL_REX_PLANET = 'Mecatol Rex'
ANTIMASS_DEFLECTORS = 'Antimass Deflectors'
WAR_SUN = 'War Sun'
CUSTODIANS_COST = 6


class IllegalAction(Exception):
    pass


@dataclasses.dataclass
class MoveOption(object):
    """A ship that can reach the active system, and the route it would take."""
    ship: Unit
    start: hexes.Hex
    path: movement.Path


@dataclasses.dataclass
class Move(object):
    option: MoveOption
    cargo: List = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ProductionContext(object):
    """What the active player may produce, worked out for the agent."""
    limit: int                     # total units that can be produced
    budget: int                    # ready planets' resources plus trade goods
    can_produce_ships: bool        # False when blockaded
    fleet_room: int                # non-fighter ships before the fleet pool is full
    fighter_room: int              # fighters before capacity is exceeded
    plastic_room: Dict[UnitType, Optional[int]]  # None means unlimited


@dataclasses.dataclass
class SpaceCannonShot(object):
    shooter: str
    target: str
    hits: int
    losses: List


@dataclasses.dataclass
class TacticalReport(object):
    player: str
    active: hexes.Hex
    moves: List[Move] = dataclasses.field(default_factory=list)
    rift_losses: List = dataclasses.field(default_factory=list)
    # Fighters and ground forces stranded in systems ships moved out of.
    left_behind: List = dataclasses.field(default_factory=list)
    space_cannon: List[SpaceCannonShot] = dataclasses.field(default_factory=list)
    defender: Optional[str] = None
    space_combat: Optional[combat.CombatResult] = None
    retreated_to: Optional[hexes.Hex] = None
    capacity_losses: Dict[str, List] = dataclasses.field(default_factory=dict)
    removed_custodians: bool = False
    invasion: Optional[invasion_lib.InvasionResult] = None
    produced: Dict[UnitType, int] = dataclasses.field(default_factory=dict)
    paid_planets: List[str] = dataclasses.field(default_factory=list)
    paid_trade_goods: int = 0


# Options offered to agents.

def ActivationOptions(state, player):
    """{coord: [MoveOption]} for every system the player may activate."""
    coords = [c for c, s in state.board.systems.items()
              if player not in s.command_tokens]
    reach = _ReachByShip(state, player)
    return {c: [MoveOption(ship, start, paths[c])
                for ship, start, paths in reach if c in paths and c != start]
            for c in coords}


def _ReachByShip(state, player, extra_tokens=()):
    """(ship, start, {coord: Path}) for every ship that can move."""
    tokens = set(state.CommandTokensOnBoard(player)) | set(extra_tokens)
    antimass = ANTIMASS_DEFLECTORS in state.Player(player).technologies
    cache = {}
    result = []
    for coord, system in state.board.systems.items():
        if coord in tokens:
            continue
        for ship in system.ShipsOf(player):
            if ship.movement <= 0:
                continue
            key = (coord, ship.movement)
            if key not in cache:
                cache[key] = movement.ReachableSystems(
                    state.board, coord, ship.movement, player, antimass, no_pass=tokens)
            result.append((ship, coord, cache[key]))
    return result


def MoveOptions(state, player, active):
    """Ships that can move into the (already activated) active system."""
    tokens = set(state.CommandTokensOnBoard(player)) - {active}
    return [MoveOption(ship, start, paths[active])
            for ship, start, paths in _ReachByShip(state, player)
            if start not in tokens and start != active and active in paths]


def Transportable(state, player, coord):
    """Fighters and ground forces a ship starting at coord could carry: from
    the space area and from the player's planets there."""
    system = state.board.SystemAt(coord)
    units = [u for u in system.UnitsInSpace(player)
             if u.unit_type == UnitType.FIGHTER or u.IsGroundForce()]
    for planet in system.planets:
        units += planet.GroundForces(player)
    return units


def RetreatOptions(state, player, coord):
    """Adjacent systems with no other players' ships, holding the player's
    units or a planet they control."""
    options = []
    for c in state.board.Adjacent(coord):
        system = state.board.SystemAt(c)
        if system.HasOtherPlayersShips(player):
            continue
        has_units = bool(system.UnitsInSpace(player)) or any(
            p.UnitsOf(player) for p in system.planets)
        controls = any(p.controller == player for p in system.planets)
        if has_units or controls:
            options.append(c)
    return options


# The action.

def TakeTacticalAction(state, player, agents=None, dice=None, listener=None):
    """Run one tactical action for `player`. Returns a TacticalReport.

    listener, if given, follows each combat as it happens (see
    combat._Combat), with kind= ('space' or 'ground'), system= (its label),
    attacker= and defender= added, and planet= for ground combat.
    """
    agents = dict(agents or {})
    for p in state.players:
        agents.setdefault(p.name, agents_lib.GreedyAgent())
    dice = dice if dice is not None else dice_lib.Dice()
    turn = _Turn(state, player, agents, dice, listener)
    turn.Activate()
    turn.Move()
    turn.SpaceCannonOffense()
    turn.SpaceCombat()
    turn.Invade()
    turn.Produce()
    return turn.report


class _Turn(object):
    def __init__(self, state, player, agents, dice, listener=None):
        self.state = state
        self.player = player
        self.agents = agents
        self.dice = dice
        self.listener = listener
        self.report = None
        self.active = None

    @property
    def system(self):
        return self.state.board.SystemAt(self.active)

    def _Listener(self, **context):
        """A combat listener that adds where (and what) the combat is."""
        if not self.listener:
            return None

        def Listen(event, **details):
            self.listener(event, system=self.system.Label(), **dict(context, **details))
        return Listen

    def _Agent(self, player):
        return self.agents[player]

    # Step 1.
    def Activate(self):
        player = self.state.Player(self.player)
        if player.tactic_tokens < 1:
            raise IllegalAction("%s has no tactic tokens" % self.player)
        options = ActivationOptions(self.state, self.player)
        choice = self._Agent(self.player).ChooseActivation(self.state, self.player, options)
        if choice not in options:
            raise IllegalAction("%s can't activate %r" % (self.player, choice))
        self.active = choice
        player.tactic_tokens -= 1
        self.system.command_tokens.add(self.player)
        self.report = TacticalReport(self.player, choice)
        self.state.Log('activated', player=self.player, system=self.system.tile_id)

    # Step 2.
    def Move(self):
        options = MoveOptions(self.state, self.player, self.active)
        if not options:
            return
        transportable = {o.start: Transportable(self.state, self.player, o.start)
                         for o in options}
        moves = self._Agent(self.player).ChooseMovement(
            self.state, self.player, self.active, list(options),
            {k: list(v) for k, v in transportable.items()})
        moves = [m if isinstance(m, Move) else Move(*m) for m in moves]
        self._ValidateMoves(moves, options, transportable)
        for move in moves:
            self._ExecuteMove(move)
        # Fighters and ground forces left behind without enough capacity are lost.
        for start in sorted({m.option.start for m in moves}):
            lost = limits.EnforceCapacity(self.state, start, self.player,
                                          self._Agent(self.player))
            if lost:
                self.report.left_behind += lost
        limits.EnforceFleetPool(self.state, self.active, self.player,
                                self._Agent(self.player))

    def _ValidateMoves(self, moves, options, transportable):
        seen, carried = set(), set()
        for move in moves:
            if all(move.option is not o for o in options) or id(move.option.ship) in seen:
                raise IllegalAction("Not a legal move (or a ship moved twice)")
            seen.add(id(move.option.ship))
            if len(move.cargo) > move.option.ship.capacity_limit:
                raise IllegalAction("%r can't carry %d units" % (move.option.ship,
                                                                  len(move.cargo)))
            for unit in move.cargo:
                if (all(unit is not u for u in transportable[move.option.start])
                        or id(unit) in carried):
                    raise IllegalAction("%r can't be carried (or is carried twice)" % unit)
                carried.add(id(unit))

    def _ExecuteMove(self, move):
        start = self.state.board.SystemAt(move.option.start)
        for unit in [move.option.ship] + move.cargo:
            _RemoveFromSystem(start, self.player, unit)
        survived = all(movement.SurvivesGravityRift(self.dice)
                       for _ in range(move.option.path.rifts_exited))
        if not survived:
            lost = [move.option.ship] + move.cargo
            self.report.rift_losses += lost
            self.state.Log('destroyed_by_gravity_rift', player=self.player,
                           units=[u.unit_type.name for u in lost])
            return
        for unit in [move.option.ship] + move.cargo:
            self.system.AddUnit(self.player, unit)
        self.report.moves.append(move)
        self.state.Log('moved', player=self.player, ship=move.option.ship.unit_type.name,
                       start=start.tile_id, to=self.system.tile_id,
                       cargo=[u.unit_type.name for u in move.cargo])

    def SpaceCannonOffense(self):
        order = _SeatOrderFrom(self.state, self.player)
        for shooter in order:
            cannons = [u for planet in self.system.planets for u in planet.UnitsOf(shooter)
                       if u.stats.space_cannon is not None]
            cannons += [u for u in self.system.ShipsOf(shooter)
                        if u.stats.space_cannon is not None]
            if not cannons:
                continue
            if shooter == self.player:
                targets = [p for p in self.system.PlayersWithShips() if p != shooter]
            else:
                targets = [self.player] if self.system.ShipsOf(self.player) else []
            if not targets:
                continue
            target = targets[0]
            hits = sum(u.GenerateSpaceCannon(self.dice) for u in cannons)
            losses = combat.AssignAndApplyHits(list(self.system.ShipsOf(target)),
                                               self._Agent(target), hits)
            _RemoveAll(self.system, target, losses)
            self.report.space_cannon.append(SpaceCannonShot(shooter, target, hits, losses))
            self.state.Log('space_cannon_offense', shooter=shooter, target=target,
                           hits=hits, losses=[u.unit_type.name for u in losses])

    # Step 3.
    def SpaceCombat(self):
        self._Fight()
        # Excess fighters and ground forces are destroyed at the end of combat
        # (and when space cannon fire left them short, even with no combat).
        for p in list(self.system.space):
            lost = limits.EnforceCapacity(self.state, self.active, p, self._Agent(p))
            if lost:
                self.report.capacity_losses[p] = lost

    def _Fight(self):
        others = [p for p in self.system.PlayersWithShips() if p != self.player]
        if not others or not self.system.ShipsOf(self.player):
            return
        defender = others[0]
        retreats = {p: RetreatOptions(self.state, p, self.active)
                    for p in (self.player, defender)}
        result = combat.SpaceCombat(
            self.system.ShipsOf(self.player), self.system.ShipsOf(defender),
            attacker_agent=self._Agent(self.player), defender_agent=self._Agent(defender),
            dice=self.dice,
            attacker_can_retreat=bool(retreats[self.player]),
            defender_can_retreat=bool(retreats[defender]),
            listener=self._Listener(kind='space', attacker=self.player,
                                    defender=defender)).Resolve()
        for p, survivors in ((self.player, result.attacker_units),
                             (defender, result.defender_units)):
            others_in_space = [u for u in self.system.UnitsInSpace(p) if not u.IsShip()]
            self.system.space[p] = list(survivors) + others_in_space
        self.report.defender = defender
        self.report.space_combat = result
        self.state.Log('space_combat', attacker=self.player, defender=defender,
                       winner={combat.ATTACKER: self.player,
                               combat.DEFENDER: defender}.get(result.winner),
                       rounds=len(result.rounds))
        if result.retreated:
            retreating = self.player if result.retreated == combat.ATTACKER else defender
            self._Retreat(retreating, retreats[retreating])

    def _Retreat(self, player, options):
        choice = self._Agent(player).ChooseRetreatSystem(self.state, player, list(options))
        if choice not in options:
            raise IllegalAction("%s can't retreat to %r" % (player, choice))
        destination = self.state.board.SystemAt(choice)
        for unit in self.system.UnitsInSpace(player):
            destination.AddUnit(player, unit)
        self.system.space[player] = []
        if (player not in destination.command_tokens
                and self.state.ReinforcementTokens(player) > 0):
            destination.command_tokens.add(player)
        self.report.retreated_to = choice
        self.state.Log('retreated', player=player, to=destination.tile_id)
        limits.EnforceFleetPool(self.state, choice, player, self._Agent(player))
        limits.EnforceCapacity(self.state, choice, player, self._Agent(player))

    # Step 4.
    def Invade(self):
        if self.system.HasOtherPlayersShips(self.player):
            return
        ships = self.system.ShipsOf(self.player)
        ground = [u for u in self.system.UnitsInSpace(self.player) if u.IsGroundForce()]
        if ground:
            self._MaybeRemoveCustodians()
        planets = [p for p in self.system.planets
                   if not (self.state.custodians and p.name == MECATOL_REX_PLANET)]
        if not planets or not (ground or any(s.stats.bombardment for s in ships)):
            return
        before = {p.name: p.controller for p in planets}
        result = invasion_lib.Invasion(self.player, ships, ground, planets,
                                       agents=self.agents, dice=self.dice,
                                       listener=self._Listener(kind='ground')).Resolve()
        self.system.space[self.player] = ships + result.ground_forces_in_space
        self.report.invasion = result
        for planet in planets:
            if planet.controller == self.player and before[planet.name] != self.player:
                self.state.Log('planet_gained', player=self.player, planet=planet.name,
                               previous=before[planet.name])

    def _MaybeRemoveCustodians(self):
        """Before landing on Mecatol Rex, the custodians token must be
        removed by spending 6 influence, which scores 1 victory point."""
        if not self.state.custodians or not any(
                p.name == MECATOL_REX_PLANET for p in self.system.planets):
            return
        if Spendable(self.state, self.player, 'influence') < CUSTODIANS_COST:
            return
        if not self._Agent(self.player).ChooseRemoveCustodians(
                self.state, self.player, CUSTODIANS_COST):
            return
        planets, trade_goods = PayInfluence(self.state, self.player, CUSTODIANS_COST)
        self.state.custodians = False
        self.state.Player(self.player).victory_points += 1
        self.report.removed_custodians = True
        self.state.Log('custodians_removed', player=self.player, exhausted=planets,
                       trade_goods=trade_goods)

    # Step 5.
    def Produce(self):
        dock_planets = [p for p in self.system.planets
                        if any(u.unit_type == UnitType.SPACEDOCK for u in p.UnitsOf(self.player))]
        if not dock_planets:
            return
        player = self.state.Player(self.player)
        context = self._ProductionContext(player, dock_planets)
        choice = self._Agent(self.player).ChooseProduction(
            self.state, self.player, self.active, context)
        choice = {t: n for t, n in (choice or {}).items() if n}
        if not choice:
            return
        cost = self._ValidateProduction(choice, context)
        new_units = []
        for unit_type, count in choice.items():
            for _ in range(count):
                unit = Unit(unit_type)
                new_units.append(unit)
                if unit.IsShip():
                    self.system.AddUnit(self.player, unit)
                else:
                    dock_planets[0].AddUnit(self.player, unit)
        if (limits.CapacityExcess(self.system, self.player)
                or limits.FleetPoolExcess(self.system, self.player, player.fleet_tokens)):
            for unit in new_units:
                _RemoveFromSystem(self.system, self.player, unit)
            raise IllegalAction("Production would exceed capacity or the fleet pool")
        self.report.paid_planets, self.report.paid_trade_goods = PayResources(
            self.state, self.player, cost)
        self.report.produced = choice
        self.state.Log('produced', player=self.player, system=self.system.tile_id,
                       units={t.name: n for t, n in choice.items()}, cost=cost,
                       exhausted=self.report.paid_planets,
                       trade_goods=self.report.paid_trade_goods)

    def _ProductionContext(self, player, dock_planets):
        limit = sum(p.resources + Unit(UnitType.SPACEDOCK).stats.production
                    for p in dock_planets)
        budget = (sum(p.resources for p in player.ReadyPlanets(self.state.board))
                  + player.trade_goods)
        blockaded = (self.system.HasOtherPlayersShips(self.player)
                     and not self.system.ShipsOf(self.player))
        fleet_room = player.fleet_tokens - len(limits.FleetPoolShips(self.system, self.player))
        fighters = sum(1 for u in self.system.UnitsInSpace(self.player)
                       if u.unit_type == UnitType.FIGHTER)
        ground = sum(1 for u in self.system.UnitsInSpace(self.player) if u.IsGroundForce())
        free = limits.FIGHTERS_FREE_PER_SPACE_DOCK * len(dock_planets)
        fighter_room = max(0, limits.Capacity(self.system, self.player) + free
                           - fighters - ground)
        plastic = {}
        for t in UnitType:
            stats = Unit(t).stats
            if stats.category == Category.STRUCTURE or stats.cost is None:
                continue
            # War suns can't be produced without their technology.
            if t == UnitType.WARSUN and WAR_SUN not in player.technologies:
                continue
            plastic[t] = (None if stats.plastic_limit is None
                          else stats.plastic_limit - self.state.UnitsOnBoard(self.player, t))
        return ProductionContext(limit, budget, not blockaded, max(0, fleet_room),
                                 fighter_room, plastic)

    def _ValidateProduction(self, choice, context):
        total = 0
        cost = 0
        for unit_type, count in choice.items():
            if not isinstance(count, int) or count < 0:
                raise IllegalAction("Bad count %r for %s" % (count, unit_type))
            if unit_type not in context.plastic_room:
                raise IllegalAction("%s can't be produced" % unit_type.name)
            unit = Unit(unit_type)
            if unit.IsShip() and not context.can_produce_ships:
                raise IllegalAction("A blockaded space dock can't produce ships")
            room = context.plastic_room[unit_type]
            if room is not None and count > room:
                raise IllegalAction("Not enough %s left in reinforcements" % unit_type.name)
            total += count
            per = unit.stats.units_per_cost
            cost += -(-count // per) * unit.stats.cost
        if total > context.limit:
            raise IllegalAction("Producing %d units; the limit is %d" % (total, context.limit))
        if cost > context.budget:
            raise IllegalAction("Costs %d; only %d available" % (cost, context.budget))
        return cost


def PayResources(state, player, cost):
    """Pay `cost` resources by exhausting planets and spending trade goods,
    wasting as little as possible: least overspend, then fewest trade goods,
    then least influence tied up. Returns (planet names, trade goods)."""
    return _Pay(state, player, cost, 'resources', 'influence')


def PayInfluence(state, player, cost):
    """Like PayResources, but spending influence."""
    return _Pay(state, player, cost, 'influence', 'resources')


def Spendable(state, player, value):
    """Ready planets' total `value` ('resources' or 'influence') plus trade goods."""
    p = state.Player(player)
    return sum(getattr(pl, value) for pl in p.ReadyPlanets(state.board)) + p.trade_goods


def _Pay(state, player, cost, value, other):
    p = state.Player(player)
    ready = [pl for pl in p.ReadyPlanets(state.board) if getattr(pl, value) > 0]
    best = None
    for mask in range(1 << len(ready)):
        chosen = [pl for i, pl in enumerate(ready) if mask >> i & 1]
        paid = sum(getattr(pl, value) for pl in chosen)
        trade_goods = max(0, cost - paid)
        if trade_goods > p.trade_goods:
            continue
        score = (paid + trade_goods - cost, trade_goods,
                 sum(getattr(pl, other) for pl in chosen), len(chosen))
        if best is None or score < best[0]:
            best = (score, chosen, trade_goods)
    if best is None:
        raise IllegalAction("%s can't pay %d %s" % (player, cost, value))
    _, chosen, trade_goods = best
    for planet in chosen:
        planet.exhausted = True
    p.trade_goods -= trade_goods
    return [pl.name for pl in chosen], trade_goods


def _SeatOrderFrom(state, player):
    names = [p.name for p in state.players]
    i = names.index(player)
    return names[i:] + names[:i]


def _RemoveFromSystem(system, player, unit):
    for units in [system.UnitsInSpace(player)] + [p.UnitsOf(player) for p in system.planets]:
        for i, u in enumerate(units):
            if u is unit:
                del units[i]
                return
    raise ValueError("%r isn't in %r" % (unit, system))


def _RemoveAll(system, player, units):
    for unit in units:
        _RemoveFromSystem(system, player, unit)


def DescribeReport(state, report):
    """A readable account of a tactical action."""
    system = state.board.SystemAt(report.active)
    lines = ['%s activates %s.' % (report.player, _Name(system))]
    for move in report.moves:
        start = state.board.SystemAt(move.option.start)
        route = ' > '.join(state.board.SystemAt(c).Label() for c in move.option.path.systems)
        cargo = ' carrying %s' % game_lib.DescribeUnits(move.cargo) if move.cargo else ''
        lines.append('  moves %s from %s (%s)%s' % (
            move.option.ship.unit_type.name.lower(), start.Label(), route, cargo))
    if report.rift_losses:
        lines.append('  lost to the gravity rift: %s' % game_lib.DescribeUnits(report.rift_losses))
    if report.left_behind:
        lines.append('  left behind without capacity, and lost: %s' %
                     game_lib.DescribeUnits(report.left_behind))
    for shot in report.space_cannon:
        lines.append('  space cannon: %s fires at %s, %d hit(s)%s' % (
            shot.shooter, shot.target, shot.hits,
            ', destroying %s' % game_lib.DescribeUnits(shot.losses) if shot.losses else ''))
    if report.space_combat:
        result = report.space_combat
        winner = {combat.ATTACKER: report.player,
                  combat.DEFENDER: report.defender}.get(result.winner, 'nobody (draw)')
        lines.append('  space combat with %s: %d round(s), won by %s' % (
            report.defender, len(result.rounds), winner))
        if result.retreated:
            lines.append('  %s retreats to %s' % (
                report.player if result.retreated == combat.ATTACKER else report.defender,
                state.board.SystemAt(report.retreated_to).Label()))
    for player, lost in report.capacity_losses.items():
        lines.append('  %s loses %s beyond capacity' % (player, game_lib.DescribeUnits(lost)))
    if report.removed_custodians:
        lines.append('  spends 6 influence to remove the custodians token (+1 victory point)')
    if report.invasion:
        for r in report.invasion.reports:
            bits = []
            if r.bombardment_hits:
                bits.append('bombardment %d hit(s)' % r.bombardment_hits)
            if r.committed:
                bits.append('lands %s' % game_lib.DescribeUnits(r.committed))
            if r.space_cannon_hits:
                bits.append('space cannon defense %d hit(s)' % r.space_cannon_hits)
            if r.ground_combat:
                bits.append('ground combat %d round(s)' % len(r.ground_combat.rounds))
            if r.gained_control:
                bits.append('takes control')
            if bits:
                lines.append('  %s: %s' % (r.planet.name, ', '.join(bits)))
    if report.produced:
        paid = ', '.join(report.paid_planets) or 'nothing'
        if report.paid_trade_goods:
            paid += ' + %d trade good(s)' % report.paid_trade_goods
        lines.append('  produces %s (exhausting %s)' % (
            game_lib.DescribeUnits([Unit(t) for t, n in report.produced.items()
                                    for _ in range(n)]), paid))
    return '\n'.join(lines) + '\n'


def _Name(system):
    if system.planets:
        return '%s (%s)' % (system.Label(), ', '.join(p.name for p in system.planets))
    return system.Label()
