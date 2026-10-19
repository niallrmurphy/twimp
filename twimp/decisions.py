#!/usr/bin/env python3
# Agent choices as structured decisions.
#
# A DecisionAgent turns each Agent method into a Decision: a kind, a prompt,
# JSON-friendly data describing the options, a JSON default answer (what
# the GreedyAgent would do), and a parse function that checks a JSON answer
# and converts it back into what the engine expects. Subclasses implement
# Ask(decision), which returns the parsed result. The web server's agent
# asks a browser; DefaultingAgent just accepts the defaults (for tests).
#
# Systems are identified by "q,r" keys, and units by their index in the
# list the decision shows.

import dataclasses
from typing import Any, Callable, Dict

from twimp import agents
from twimp import game as game_lib
from twimp.units import UNIT_STATS, UnitType


def Key(coord):
    return '%d,%d' % (coord.q, coord.r)


def UnitName(unit):
    return unit.unit_type.name.lower()


def _Indices(answer, count, what='units'):
    if not isinstance(answer, list) or not all(isinstance(i, int) for i in answer):
        raise ValueError('Expected a list of %s' % what)
    for i in answer:
        if not 0 <= i < count:
            raise ValueError('No such choice: %d' % i)
    return answer


def _Bool(answer):
    if not isinstance(answer, bool):
        raise ValueError('Expected yes or no')
    return answer


@dataclasses.dataclass
class Decision(object):
    kind: str
    player: str
    prompt: str
    data: Dict[str, Any]
    default: Any
    parse: Callable[[Any], Any]
    id: int = 0

    def ToJson(self):
        return {'id': self.id, 'kind': self.kind, 'player': self.player,
                'prompt': self.prompt, 'data': self.data, 'default': self.default}


class DecisionAgent(agents.Agent):
    def __init__(self, name):
        self.name = name
        self.suggest = agents.GreedyAgent()

    def Ask(self, decision):
        raise NotImplementedError

    def _Ask(self, kind, prompt, data, default, parse):
        return self.Ask(Decision(kind, self.name, prompt, data, default, parse))

    # Rounds.

    def ChooseAction(self, state, player, options):
        def Parse(answer):
            if answer not in options:
                raise ValueError('Choose one of %s' % ', '.join(options))
            return answer
        p = state.Player(player)
        return self._Ask(
            'action', 'Your turn: take a tactical action, or pass?',
            {'options': list(options), 'tactic_tokens': p.tactic_tokens},
            self.suggest.ChooseAction(state, player, options), Parse)

    def ChooseRemoveCustodians(self, state, player, cost):
        return self._Ask(
            'custodians', 'Spend %d influence to remove the custodians token from '
            'Mecatol Rex (scoring 1 victory point) so your ground forces can land?' % cost,
            {'cost': cost}, True, _Bool)

    def ChooseCommandTokens(self, state, player, total):
        p = state.Player(player)

        def Parse(answer):
            if (not isinstance(answer, list) or len(answer) != 3
                    or not all(isinstance(n, int) and n >= 0 for n in answer)):
                raise ValueError('Enter three numbers')
            if sum(answer) != total:
                raise ValueError('They must add up to %d' % total)
            return tuple(answer)

        return self._Ask(
            'command_tokens', 'Status phase: split your %d command tokens between your '
            'tactic, fleet and strategy pools.' % total,
            {'total': total,
             'current': [p.tactic_tokens, p.fleet_tokens, p.strategy_tokens]},
            list(self.suggest.ChooseCommandTokens(state, player, total)), Parse)

    # The tactical action.

    def ChooseActivation(self, state, player, options):
        keys = {Key(c): c for c in options}
        systems = []
        for coord, movers in options.items():
            system = state.board.SystemAt(coord)
            systems.append({
                'key': Key(coord), 'label': system.Label(),
                'movers': len(movers),
                'enemies': [p for p in system.PlayersWithShips() if p != player],
            })

        def Parse(answer):
            if answer not in keys:
                raise ValueError("You can't activate that system")
            return keys[answer]

        return self._Ask(
            'activation', 'Choose a system to activate. Highlighted systems are ones '
            'your ships can reach.', {'systems': systems},
            Key(self.suggest.ChooseActivation(state, player, options)), Parse)

    def ChooseMovement(self, state, player, active, options, transportable):
        ships = []
        for i, option in enumerate(options):
            pool = transportable.get(option.start, [])
            ships.append({
                'index': i, 'unit': UnitName(option.ship),
                'damaged': option.ship.damaged,
                'start': Key(option.start),
                'start_label': state.board.SystemAt(option.start).Label(),
                'route': [state.board.SystemAt(c).Label() for c in option.path.systems],
                'rifts': option.path.rifts_exited,
                'capacity': option.ship.capacity_limit,
            })
        available = {}
        for start, pool in transportable.items():
            available[Key(start)] = {
                'ground': sum(1 for u in pool if u.IsGroundForce()),
                'fighters': sum(1 for u in pool if u.unit_type == UnitType.FIGHTER)}
        greedy = self.suggest.ChooseMovement(state, player, active, options, transportable)
        default = [{'ship': options.index(o), 'ground': sum(1 for u in c if u.IsGroundForce()),
                    'fighters': sum(1 for u in c if u.unit_type == UnitType.FIGHTER)}
                   for o, c in greedy]

        def Parse(answer):
            if not isinstance(answer, list):
                raise ValueError('Expected a list of moves')
            moves, used, seen = [], set(), set()
            for move in answer:
                try:
                    i, ground, fighters = (int(move['ship']), int(move.get('ground', 0)),
                                           int(move.get('fighters', 0)))
                except (TypeError, KeyError, ValueError):
                    raise ValueError('Each move needs a ship, and ground/fighter counts')
                if not 0 <= i < len(options) or i in seen:
                    raise ValueError('Bad ship choice')
                seen.add(i)
                option = options[i]
                if ground < 0 or fighters < 0:
                    raise ValueError('Counts must not be negative')
                if ground + fighters > option.ship.capacity_limit:
                    raise ValueError('A %s can carry %d' % (UnitName(option.ship),
                                                           option.ship.capacity_limit))
                pool = [u for u in transportable.get(option.start, []) if id(u) not in used]
                g = _GroundForcesInPickUpOrder(state, player, option.start, pool)[:ground]
                f = [u for u in pool if u.unit_type == UnitType.FIGHTER][:fighters]
                if len(g) < ground or len(f) < fighters:
                    raise ValueError('Not enough ground forces or fighters at %s' %
                                     state.board.SystemAt(option.start).Label())
                used.update(id(u) for u in g + f)
                moves.append((option, g + f))
            return moves

        return self._Ask(
            'movement', 'Choose ships to move into %s, and what they carry.' %
            state.board.SystemAt(active).Label(),
            {'active': Key(active), 'ships': ships, 'available': available},
            default, Parse)

    def ChooseRetreatSystem(self, state, player, options):
        keys = {Key(c): c for c in options}

        def Parse(answer):
            if answer not in keys:
                raise ValueError("You can't retreat there")
            return keys[answer]

        return self._Ask(
            'retreat_system', 'Choose where to retreat to.',
            {'systems': [{'key': Key(c), 'label': state.board.SystemAt(c).Label()}
                         for c in options]},
            Key(self.suggest.ChooseRetreatSystem(state, player, options)), Parse)

    def ChooseProduction(self, state, player, coord, context):
        units = []
        for unit_type, room in context.plastic_room.items():
            stats = UNIT_STATS[unit_type]
            units.append({'type': unit_type.name.lower(), 'cost': stats.cost,
                          'per_cost': stats.units_per_cost, 'room': room})
        names = {t.name.lower(): t for t in context.plastic_room}

        def Parse(answer):
            if not isinstance(answer, dict):
                raise ValueError('Expected unit counts')
            choice = {}
            for name, count in answer.items():
                if name not in names or not isinstance(count, int) or count < 0:
                    raise ValueError('Bad production entry %r' % name)
                if count:
                    choice[names[name]] = count
            problem = agents.ProductionProblem(choice, context)
            if problem:
                raise ValueError(problem)
            return choice

        greedy = self.suggest.ChooseProduction(state, player, coord, context)
        return self._Ask(
            'production', 'Produce units at %s.' % state.board.SystemAt(coord).Label(),
            {'limit': context.limit, 'budget': context.budget,
             'can_produce_ships': context.can_produce_ships,
             'fleet_room': context.fleet_room, 'fighter_room': context.fighter_room,
             'units': units},
            {t.name.lower(): n for t, n in greedy.items()}, Parse)

    # Combat and invasion.

    def AssignHits(self, units, hits):
        def Parse(answer):
            picks = _Indices(answer, len(units))
            if len(picks) != hits:
                raise ValueError('Assign exactly %d hit(s)' % hits)
            for i in set(picks):
                if picks.count(i) > units[i].CanHandleDamage():
                    raise ValueError('That %s can only take %d hit(s)' % (
                        UnitName(units[i]), units[i].CanHandleDamage()))
            return [units[i] for i in picks]

        default = [units.index(u) for u in self.suggest.AssignHits(units, hits)]
        return self._Ask(
            'hits', 'Assign %d hit(s) to your units. Ships with Sustain Damage can '
            'take two.' % hits,
            {'hits': hits, 'units': [{'index': i, 'unit': UnitName(u), 'damaged': u.damaged,
                                      'can_take': u.CanHandleDamage()}
                                     for i, u in enumerate(units)]},
            [i for i in default], Parse)

    def DeclareRetreat(self, own_units, enemy_units, round_number):
        return self._Ask(
            'retreat', 'Space combat, round %d: retreat at the end of this round?' %
            round_number,
            {'round': round_number, 'own': game_lib.DescribeUnits(own_units),
             'enemy': game_lib.DescribeUnits(enemy_units)},
            False, _Bool)

    def ChooseBombardment(self, player, units, planets):
        if not units or not planets:
            return []

        def Parse(answer):
            if answer is None:
                return []
            if not isinstance(answer, int) or not 0 <= answer < len(planets):
                raise ValueError('Choose a planet, or none')
            return [(u, planets[answer]) for u in units]

        greedy = self.suggest.ChooseBombardment(player, units, planets)
        return self._Ask(
            'bombardment', 'Bombard a planet with %s?' % game_lib.DescribeUnits(units),
            {'planets': [{'index': i, 'name': p.name, 'controller': p.controller,
                          'defenders': sum(len(p.GroundForces(o))
                                           for o in p.OtherPlayers(player))}
                         for i, p in enumerate(planets)]},
            planets.index(greedy[0][1]) if greedy else None, Parse)

    def CommitGroundForces(self, player, ground_forces, planets):
        if not ground_forces:
            return {}

        def Parse(answer):
            if (not isinstance(answer, list) or len(answer) != len(planets)
                    or not all(isinstance(n, int) and n >= 0 for n in answer)):
                raise ValueError('Expected a count for each planet')
            if sum(answer) > len(ground_forces):
                raise ValueError('You only have %d ground force(s)' % len(ground_forces))
            remaining = list(ground_forces)
            choice = {}
            for planet, n in zip(planets, answer):
                if n:
                    choice[planet], remaining = remaining[:n], remaining[n:]
            return choice

        greedy = self.suggest.CommitGroundForces(player, ground_forces, planets)
        return self._Ask(
            'landing', 'Land your %d ground force(s) on planets.' % len(ground_forces),
            {'forces': len(ground_forces),
             'planets': [{'index': i, 'name': p.name, 'controller': p.controller,
                          'defenders': sum(len(p.GroundForces(o))
                                           for o in p.OtherPlayers(player))}
                         for i, p in enumerate(planets)]},
            [len(greedy.get(p, [])) for p in planets], Parse)

    def ChooseUnitsToRemove(self, units, count):
        def Parse(answer):
            picks = _Indices(answer, len(units))
            if len(picks) != count or len(set(picks)) != count:
                raise ValueError('Choose %d different units' % count)
            return [units[i] for i in picks]

        default = [units.index(u) for u in self.suggest.ChooseUnitsToRemove(units, count)]
        return self._Ask(
            'remove', 'You are over a limit: choose %d unit(s) to remove.' % count,
            {'count': count, 'units': [{'index': i, 'unit': UnitName(u), 'damaged': u.damaged}
                                       for i, u in enumerate(units)]},
            default, Parse)


def _GroundForcesInPickUpOrder(state, player, start, pool):
    """Which ground forces to take first: those in space, then spares from
    each planet, and only then the last one guarding each planet."""
    available = {id(u) for u in pool}
    system = state.board.SystemAt(start)
    order = [u for u in system.UnitsInSpace(player) if u.IsGroundForce()]
    planets = [p.GroundForces(player) for p in system.planets]
    for forces in planets:
        order += forces[1:]
    for forces in planets:
        order += forces[:1]
    return [u for u in order if id(u) in available]


class DefaultingAgent(DecisionAgent):
    """Answers every decision with its default (after a JSON round trip), so
    it should play exactly like the GreedyAgent. Used to test decisions."""
    def __init__(self, name):
        super(DefaultingAgent, self).__init__(name)
        self.asked = []

    def Ask(self, decision):
        import json
        self.asked.append(decision)
        return decision.parse(json.loads(json.dumps(decision.default)))
