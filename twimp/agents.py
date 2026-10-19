#!/usr/bin/env python3
# Player decision interface. The rules engine never makes a choice a player
# would make; it asks an Agent.

import random

from twimp.units import UNIT_STATS, UnitType

MECATOL_REX = 'Mecatol Rex'


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

    def ChooseUnitsToRemove(self, units, count):
        """Choose `count` of these units to remove, e.g. fighters beyond
        capacity or ships beyond the fleet pool. Returns a list of Units."""
        raise NotImplementedError

    # Tactical action choices (see tactical.py).

    def ChooseActivation(self, state, player, options):
        """Choose a system to activate.

        Args:
          options: {coord: [MoveOption]}: every system we may activate, with
            the ships that could move into it.
        Returns:
          one of the coords.
        """
        raise NotImplementedError

    def ChooseMovement(self, state, player, active, options, transportable):
        """Choose which ships move into the active system, and what they carry.

        Args:
          options: [MoveOption], one per ship that can reach the active system.
          transportable: {start coord: [Unit]}, fighters and ground forces each
            ship could pick up where it starts.
        Returns:
          a list of (MoveOption, [cargo units]); each ship and unit at most
          once, and no more cargo than the ship's capacity.
        """
        return []

    def ChooseRetreatSystem(self, state, player, options):
        """Choose where to retreat to, from a non-empty list of coords."""
        return options[0]

    def ChooseProduction(self, state, player, coord, context):
        """Choose units to produce at the active system's space docks.

        Args:
          context: a tactical.ProductionContext with the limit, budget, and
            room left in the fleet pool, capacity and reinforcements.
        Returns:
          {UnitType: count}.
        """
        return {}


class GreedyAgent(Agent):
    """Assigns hits to lose as little as possible and never retreats.

    Its invasion choices are deliberately simple: bombard the planet with
    the most enemy ground forces, land one ground force on each undefended
    planet we don't control, and send the rest to the weakest defended one.
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

        def Defenders(p):
            return sum(len(p.GroundForces(o)) for o in p.OtherPlayers(player))

        candidates.sort(key=lambda p: (Defenders(p), -(p.resources + p.influence)))
        forces = list(ground_forces)
        choice = {}
        # One each on undefended planets, most valuable first...
        for planet in candidates:
            if Defenders(planet) == 0 and forces:
                choice[planet] = [forces.pop(0)]
        # ...and the rest on the weakest defended planet, or the best one.
        if forces:
            defended = [p for p in candidates if Defenders(p) > 0]
            target = defended[0] if defended else candidates[0]
            choice.setdefault(target, []).extend(forces)
        return choice

    # Tactical choices: a simple plan of "take the most valuable planets we
    # can reach that no enemy ships guard, otherwise build at home".

    def ChooseActivation(self, state, player, options):
        best, best_score = None, None
        for coord, movers in options.items():
            system = state.board.SystemAt(coord)
            if not movers or system.HasOtherPlayersShips(player):
                continue
            if not any(m.ship.capacity_limit for m in movers):
                continue
            targets = [p for p in system.planets if p.controller != player
                       and not (state.custodians and p.name == MECATOL_REX)]
            if not targets:
                continue
            defenders = sum(len(p.GroundForces(o)) for p in targets
                            for o in p.OtherPlayers(player))
            score = (sum(p.resources + p.influence for p in targets) - 2 * defenders,
                     -min(len(m.path.systems) for m in movers))
            if best_score is None or score > best_score:
                best, best_score = coord, score
        if best is not None:
            return best
        home = state.HomeSystem(player)
        if home in options:
            return home
        return next(iter(options))

    def ChooseMovement(self, state, player, active, options, transportable):
        moves = []
        used = set()
        # Leave one ground force on each planet we take them from.
        keep = set()
        for start in transportable:
            for planet in state.board.SystemAt(start).planets:
                keep.update(id(u) for u in planet.GroundForces(player)[:1])
        for option in sorted(options, key=lambda o: -o.ship.capacity_limit):
            cargo = []
            pool = [u for u in transportable.get(option.start, [])
                    if id(u) not in used and id(u) not in keep]
            ground = [u for u in pool if u.IsGroundForce()]
            fighters = [u for u in pool if u.unit_type == UnitType.FIGHTER]
            for unit in ground + fighters:
                if len(cargo) == option.ship.capacity_limit:
                    break
                cargo.append(unit)
                used.add(id(unit))
            moves.append((option, cargo))
        return moves

    def ChooseProduction(self, state, player, coord, context):
        """A cruiser if there's room in the fleet pool, then infantry."""
        choice = {}
        budget, limit = context.budget, context.limit
        cruisers_left = context.plastic_room.get(UnitType.CRUISER) or 0
        if (context.can_produce_ships and context.fleet_room > 0 and cruisers_left > 0
                and budget >= 2 and limit >= 1):
            choice[UnitType.CRUISER] = 1
            budget -= 2
            limit -= 1
        infantry = min(limit, budget * 2)
        if infantry:
            choice[UnitType.INFANTRY] = infantry
        return choice

    def ChooseUnitsToRemove(self, units, count):
        """Cheapest first; fighters before infantry at the same cost."""
        def Cost(unit):
            return (unit.production_cost or 0,
                    0 if unit.unit_type == UnitType.FIGHTER else 1)
        return sorted(units, key=Cost)[:count]

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


class RandomAgent(Agent):
    """Makes a random legal choice every time. Useful for shaking out bugs:
    whatever it does, the engine must accept it or the engine is wrong."""

    def __init__(self, seed=None, rng=None):
        self.rng = rng if rng is not None else random.Random(seed)

    def AssignHits(self, units, hits):
        pending = {id(u): 0 for u in units}
        assignment = []
        while len(assignment) < hits:
            candidates = [u for u in units if u.CanHandleDamage() > pending[id(u)]]
            unit = self.rng.choice(candidates)
            pending[id(unit)] += 1
            assignment.append(unit)
        return assignment

    def DeclareRetreat(self, own_units, enemy_units, round_number):
        return self.rng.random() < 0.15

    def ChooseBombardment(self, player, units, planets):
        return [(u, self.rng.choice(planets)) for u in units
                if planets and self.rng.random() < 0.8]

    def CommitGroundForces(self, player, ground_forces, planets):
        choice = {}
        for unit in ground_forces:
            target = self.rng.choice(list(planets) + [None])
            if target is not None:
                choice.setdefault(target, []).append(unit)
        return choice

    def ChooseUnitsToRemove(self, units, count):
        return self.rng.sample(list(units), count)

    def ChooseActivation(self, state, player, options):
        with_movers = [c for c, movers in options.items() if movers]
        if with_movers and self.rng.random() < 0.8:
            return self.rng.choice(with_movers)
        return self.rng.choice(list(options))

    def ChooseMovement(self, state, player, active, options, transportable):
        used = set()
        moves = []
        for option in options:
            if self.rng.random() < 0.3:
                continue
            pool = [u for u in transportable.get(option.start, []) if id(u) not in used]
            self.rng.shuffle(pool)
            cargo = pool[:self.rng.randint(0, option.ship.capacity_limit)]
            used.update(id(u) for u in cargo)
            moves.append((option, cargo))
        return moves

    def ChooseRetreatSystem(self, state, player, options):
        return self.rng.choice(options)

    def ChooseProduction(self, state, player, coord, context):
        choice = {}
        budget, limit = context.budget, context.limit
        fleet_room, fighter_room = context.fleet_room, context.fighter_room
        plastic = dict(context.plastic_room)
        for _ in range(limit):
            options = []
            for unit_type, room in plastic.items():
                if room is not None and room <= 0:
                    continue
                if unit_type == UnitType.INFANTRY:
                    options.append(unit_type)
                elif unit_type == UnitType.FIGHTER:
                    if context.can_produce_ships and fighter_room > 0:
                        options.append(unit_type)
                elif context.can_produce_ships and fleet_room > 0:
                    options.append(unit_type)
            if not options or self.rng.random() < 0.3:
                break
            unit_type = self.rng.choice(options)
            trial = dict(choice)
            trial[unit_type] = trial.get(unit_type, 0) + 1
            if _Cost(trial) > budget:
                break
            choice = trial
            if plastic[unit_type] is not None:
                plastic[unit_type] -= 1
            if unit_type == UnitType.FIGHTER:
                fighter_room -= 1
            elif unit_type != UnitType.INFANTRY:
                fleet_room -= 1
        return choice


def _Cost(choice):
    """Resources needed for {UnitType: count}; fighters and infantry are 1 for 2."""
    total = 0
    for unit_type, count in choice.items():
        stats = UNIT_STATS[unit_type]
        total += -(-count // stats.units_per_cost) * stats.cost
    return total
