#!/usr/bin/env python3
# An Agent that asks a person at the terminal for every choice.
#
# Each prompt shows what the GreedyAgent would do; pressing Enter accepts
# that suggestion. Bad input is explained and asked for again.

from twimp import agents
from twimp import game as game_lib
from twimp.units import UnitType


class CliAgent(agents.Agent):
    def __init__(self, name=None, input_fn=input, print_fn=print):
        self.name = name
        self.input = input_fn
        self.print = print_fn
        self.suggest = agents.GreedyAgent()

    # Plumbing.

    def _Ask(self, prompt, parse, default):
        """Ask until parse(text) succeeds. Blank input (or end of input)
        returns the default."""
        while True:
            try:
                text = self.input(prompt).strip()
            except EOFError:
                return default
            if not text:
                return default
            try:
                return parse(text)
            except ValueError as e:
                self.print('  %s' % e)

    def _Numbers(self, text, count):
        """Parse '1, 3 3' into zero-based indices, each within range."""
        result = []
        for part in text.replace(',', ' ').split():
            if not part.isdigit() or not 1 <= int(part) <= count:
                raise ValueError("%r isn't a number from 1 to %d" % (part, count))
            result.append(int(part) - 1)
        return result

    def _Header(self, text):
        self.print('')
        self.print('[%s] %s' % (self.name or 'you', text))

    @staticmethod
    def _Unit(unit):
        return unit.unit_type.name.lower() + (' (damaged)' if unit.damaged else '')

    # Combat.

    def AssignHits(self, units, hits):
        default = self.suggest.AssignHits(units, hits)
        self._Header('Assign %d hit(s) to your units:' % hits)
        for i, unit in enumerate(units, 1):
            self.print('  %d. %s' % (i, self._Unit(unit)))

        def Parse(text):
            picks = [units[i] for i in self._Numbers(text, len(units))]
            if len(picks) != hits:
                raise ValueError('Choose exactly %d (repeat a number to put two '
                                 'hits on a ship with Sustain Damage)' % hits)
            for unit in picks:
                if picks.count(unit) > unit.CanHandleDamage():
                    raise ValueError('%s can only take %d hit(s)' % (
                        self._Unit(unit), unit.CanHandleDamage()))
            return picks

        return self._Ask('  Which? [Enter: %s] ' % self._DescribeAssignment(units, default),
                         Parse, default)

    def _DescribeAssignment(self, units, assignment):
        return ' '.join(str(units.index(u) + 1) for u in assignment) or 'none'

    def DeclareRetreat(self, own_units, enemy_units, round_number):
        self._Header('Combat round %d: you have %s; they have %s.' % (
            round_number, game_lib.DescribeUnits(own_units),
            game_lib.DescribeUnits(enemy_units)))

        def Parse(text):
            if text.lower() in ('y', 'yes'):
                return True
            if text.lower() in ('n', 'no'):
                return False
            raise ValueError('Answer y or n')

        return self._Ask('  Retreat at the end of this round? [y/N] ', Parse, False)

    def ChooseRetreatSystem(self, state, player, options):
        self._Header('Retreat to:')
        for i, coord in enumerate(options, 1):
            self.print('  %d. %s' % (i, state.board.SystemAt(coord).Label()))

        def Parse(text):
            picks = self._Numbers(text, len(options))
            if len(picks) != 1:
                raise ValueError('Choose one')
            return options[picks[0]]

        return self._Ask('  Which? [Enter: 1] ', Parse, options[0])

    # Invasion.

    def ChooseBombardment(self, player, units, planets):
        default = self.suggest.ChooseBombardment(player, units, planets)
        if not units or not planets:
            return default
        self._Header('Bombard with %s. Planets:' % game_lib.DescribeUnits(units))
        for i, planet in enumerate(planets, 1):
            self.print('  %d. %s' % (i, planet.name))

        def Parse(text):
            if text.lower() == 'none':
                return []
            picks = self._Numbers(text, len(planets))
            if len(picks) != 1:
                raise ValueError("Choose one planet, or 'none'")
            return [(u, planets[picks[0]]) for u in units]

        target = default[0][1].name if default else 'none'
        return self._Ask('  Target? [Enter: %s] ' % target, Parse, default)

    def CommitGroundForces(self, player, ground_forces, planets):
        default = self.suggest.CommitGroundForces(player, ground_forces, planets)
        if not ground_forces:
            return default
        self._Header('You have %s in space. Land them:' %
                     game_lib.DescribeUnits(ground_forces))
        remaining = list(ground_forces)
        choice = {}
        for planet in planets:
            if not remaining:
                break
            defenders = sum(len(planet.GroundForces(o)) for o in planet.OtherPlayers(player))
            suggested = len(default.get(planet, []))

            def Parse(text, limit=len(remaining)):
                if not text.isdigit() or int(text) > limit:
                    raise ValueError('Enter a number from 0 to %d' % limit)
                return int(text)

            n = self._Ask('  %s (%s, %d defender(s)): how many? [Enter: %d] ' % (
                planet.name, planet.controller or 'neutral', defenders, suggested),
                Parse, min(suggested, len(remaining)))
            if n:
                choice[planet] = remaining[:n]
                remaining = remaining[n:]
        return choice

    # Limits.

    def ChooseUnitsToRemove(self, units, count):
        default = self.suggest.ChooseUnitsToRemove(units, count)
        self._Header('Remove %d unit(s) (over a limit):' % count)
        for i, unit in enumerate(units, 1):
            self.print('  %d. %s' % (i, self._Unit(unit)))

        def Parse(text):
            picks = self._Numbers(text, len(units))
            if len(set(picks)) != count or len(picks) != count:
                raise ValueError('Choose %d different units' % count)
            return [units[i] for i in picks]

        return self._Ask('  Which? [Enter: %s] ' % self._DescribeAssignment(units, default),
                         Parse, default)

    # Rounds.

    def ChooseAction(self, state, player, options):
        default = self.suggest.ChooseAction(state, player, options)
        p = state.Player(player)
        self._Header('Round %d, your turn. Tokens: %d tactic, %d fleet, %d strategy.' % (
            state.round_number, p.tactic_tokens, p.fleet_tokens, p.strategy_tokens))

        def Parse(text):
            for option in options:
                if option.startswith(text.lower()):
                    return option
            raise ValueError('Choose one of: %s' % ', '.join(options))

        return self._Ask('  %s? [Enter: %s] ' % (' or '.join(options), default),
                         Parse, default)

    def ChooseRemoveCustodians(self, state, player, cost):
        def Parse(text):
            if text.lower() in ('y', 'yes'):
                return True
            if text.lower() in ('n', 'no'):
                return False
            raise ValueError('Answer y or n')

        self._Header('Mecatol Rex: spend %d influence to remove the custodians token '
                     'and score 1 victory point, so your ground forces can land?' % cost)
        return self._Ask('  [Y/n] ', Parse, True)

    def ChooseCommandTokens(self, state, player, total):
        default = self.suggest.ChooseCommandTokens(state, player, total)
        self._Header('Status phase: split your %d command tokens between tactic, fleet '
                     'and strategy pools.' % total)

        def Parse(text):
            parts = text.replace(',', ' ').split()
            if len(parts) != 3 or not all(x.isdigit() for x in parts):
                raise ValueError('Enter three numbers')
            split = tuple(int(x) for x in parts)
            if sum(split) != total:
                raise ValueError('They must add up to %d' % total)
            return split

        return self._Ask('  Tactic fleet strategy? [Enter: %d %d %d] ' % default,
                         Parse, default)

    # The tactical action.

    def ChooseActivation(self, state, player, options):
        default = self.suggest.ChooseActivation(state, player, options)
        reachable = {c for c, movers in options.items() if movers}
        self._Header("Your tactical action. Systems your ships can reach are in "
                     "[brackets]; your home is in (parens).")
        self.print(state.board.Render(highlight=reachable, origin=state.HomeSystem(player)))
        for coord in sorted(reachable, key=lambda c: state.board.SystemAt(c).tile_id):
            system = state.board.SystemAt(coord)
            planets = ', '.join('%s %d/%d%s' % (
                p.name, p.resources, p.influence,
                '' if p.controller is None else ' (%s)' % p.controller) for p in system.planets)
            enemies = [p for p in system.PlayersWithShips() if p != player]
            self.print('  %-5s %d ship(s) can reach%s%s' % (
                system.Label(), len(options[coord]),
                '; ' + planets if planets else '',
                '; enemy ships: ' + ', '.join(enemies) if enemies else ''))

        def Parse(text):
            coord = state.board.Find(text)
            if coord is None or coord not in options:
                raise ValueError("You can't activate %r" % text)
            return coord

        return self._Ask('  Activate which tile? [Enter: %s] ' %
                         state.board.SystemAt(default).tile_id, Parse, default)

    def ChooseMovement(self, state, player, active, options, transportable):
        default = self.suggest.ChooseMovement(state, player, active, options, transportable)
        self._Header('Ships that can move into %s:' % state.board.SystemAt(active).Label())
        for i, option in enumerate(options, 1):
            route = ' > '.join(state.board.SystemAt(c).Label() for c in option.path.systems)
            extra = ', capacity %d' % option.ship.capacity_limit if option.ship.capacity_limit else ''
            risk = ', %d gravity rift roll(s)' % option.path.rifts_exited \
                if option.path.rifts_exited else ''
            self.print('  %d. %s via %s%s%s' % (i, self._Unit(option.ship), route, extra, risk))

        def Parse(text):
            if text.lower() == 'none':
                return []
            if text.lower() == 'all':
                return list(range(len(options)))
            return sorted(set(self._Numbers(text, len(options))))

        suggested = [i for i, o in enumerate(options) if any(m[0] is o for m in default)]
        picks = self._Ask("  Move which? (numbers, 'all' or 'none') [Enter: %s] " % (
            ' '.join(str(i + 1) for i in suggested) or 'none'), Parse, suggested)
        default_cargo = {id(m[0]): m[1] for m in default}
        moves, used = [], set()
        for i in picks:
            option = options[i]
            cargo = []
            if option.ship.capacity_limit:
                pool = [u for u in transportable.get(option.start, []) if id(u) not in used]
                cargo = self._ChooseCargo(option, pool, default_cargo.get(id(option), []))
                used.update(id(u) for u in cargo)
            moves.append((option, cargo))
        return moves

    def _ChooseCargo(self, option, pool, default):
        ground = [u for u in pool if u.IsGroundForce()]
        fighters = [u for u in pool if u.unit_type == UnitType.FIGHTER]
        if not ground and not fighters:
            return []
        suggested_ground = sum(1 for u in default if u.IsGroundForce())
        suggested_fighters = sum(1 for u in default if u.unit_type == UnitType.FIGHTER)
        capacity = option.ship.capacity_limit

        def Parse(text):
            parts = text.replace(',', ' ').split()
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                raise ValueError('Enter two numbers: ground forces, then fighters')
            g, f = int(parts[0]), int(parts[1])
            if g > len(ground) or f > len(fighters):
                raise ValueError('Only %d ground force(s) and %d fighter(s) available'
                                 % (len(ground), len(fighters)))
            if g + f > capacity:
                raise ValueError('Capacity is %d' % capacity)
            return g, f

        g, f = self._Ask('  %s (capacity %d): carry how many ground forces and fighters? '
                         '(%d and %d available) [Enter: %d %d] ' % (
                             self._Unit(option.ship), capacity, len(ground), len(fighters),
                             suggested_ground, suggested_fighters),
                         Parse, (suggested_ground, suggested_fighters))
        return ground[:g] + fighters[:f]

    def ChooseProduction(self, state, player, coord, context):
        default = self.suggest.ChooseProduction(state, player, coord, context)
        self._Header('Production at %s: up to %d unit(s), %d resource(s) available%s.' % (
            state.board.SystemAt(coord).Label(), context.limit, context.budget,
            '' if context.can_produce_ships else ' (blockaded: no ships)'))
        self.print('  Room for %d more non-fighter ship(s) (fleet pool) and %d fighter(s).' % (
            context.fleet_room, context.fighter_room))
        names = {t.name.lower(): t for t in context.plastic_room}

        def Parse(text):
            if text.lower() == 'none':
                return {}
            choice = {}
            for part in text.replace(' ', '').split(','):
                name, _, count = part.partition('=')
                if name not in names:
                    raise ValueError('Unknown unit %r; choose from %s' % (
                        name, ', '.join(sorted(names))))
                choice[names[name]] = choice.get(names[name], 0) + int(count or 1)
            problem = _ProductionProblem(choice, context)
            if problem:
                raise ValueError(problem)
            return choice

        return self._Ask("  Produce what? (e.g. 'cruiser=1, infantry=2', or 'none') "
                         "[Enter: %s] " % (_DescribeChoice(default) or 'none'),
                         Parse, default)


def _DescribeChoice(choice):
    return ', '.join('%s=%d' % (t.name.lower(), n) for t, n in choice.items() if n)


_ProductionProblem = agents.ProductionProblem
