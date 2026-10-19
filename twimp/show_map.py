#!/usr/bin/env python3
"""Show a map, and optionally where a ship can move from a system.

Usage:
  python3 -m twimp.show_map
  python3 -m twimp.show_map --from 26 --move 2
  python3 -m twimp.show_map --map "19 26 20 21 41 22 ..." --from 19 --move 1 --asteroids
  python3 -m twimp.show_map --show-resources

Labels are tile numbers, with a for alpha and b for beta wormholes, A for an
asteroid field, G for a gravity rift, N for a nebula, S for a supernova and
H for a home system. With --from, the start is shown in (parens) and every
system the ship can reach in [brackets]. With --show-resources, each label also
shows the system's total resources/influence, and every planet is listed.
"""

import argparse
import sys

from twimp import board as board_lib
from twimp import hexes
from twimp import movement


def PlanetLabel(system):
    """The usual label plus total resources/influence, e.g. '27 4/2'."""
    if not system.planets:
        return system.Label()
    return '%s %d/%d' % (system.Label(), system.TotalResources(),
                         system.TotalInfluence())


def PlanetTable(board):
    """One line per planet, in map order: tile, name, R/I, trait, specialty."""
    lines = ['Planets (resources/influence):']
    order = [c for c in hexes.Spiral(10) if c in board.systems]
    for coord in order:
        system = board.SystemAt(coord)
        for planet in system.planets:
            extras = ', '.join(x for x in (planet.trait, planet.tech_specialty) if x)
            lines.append(('  %-5s %-12s %d/%d  %s' % (
                system.Label(), planet.name, planet.resources, planet.influence,
                extras)).rstrip())
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--map', default=board_lib.SAMPLE_MAP,
                        help='map string (default: a sample 6-player map)')
    parser.add_argument('--from', dest='start', help='tile number to move from')
    parser.add_argument('--move', type=int, default=2, help='move value (default 2)')
    parser.add_argument('--asteroids', action='store_true',
                        help='allow moving through asteroid fields (Antimass Deflectors)')
    parser.add_argument('--show-resources', '--show_resources', dest='show_resources',
                        action='store_true',
                        help='show resources/influence on the map, and list planets')
    args = parser.parse_args(argv)
    try:
        board = board_lib.Board.FromMapString(args.map)
    except board_lib.CannotPerformException as e:
        parser.error(str(e))
    render = {}
    if args.show_resources:
        render = {'label': PlanetLabel, 'width': 10}
    if args.start is None:
        print(board.Render(**render), end='')
    else:
        ShowReach(parser, board, args, render)
    if args.show_resources:
        print()
        print(PlanetTable(board), end='')
    return 0


def ShowReach(parser, board, args, render):
    start = board.Find(args.start)
    if start is None:
        parser.error('tile %s is not on the map' % args.start)
    reachable = movement.ReachableSystems(board, start, args.move, player=None,
                                          can_pass_asteroids=args.asteroids)
    print(board.Render(highlight=set(reachable), origin=start, **render), end='')
    print()
    print('Move %d from %s reaches %d systems:' % (args.move, args.start, len(reachable)))
    for coord, path in sorted(reachable.items(),
                              key=lambda kv: (len(kv[1].systems), kv[1].rifts_exited)):
        route = ' > '.join(board.SystemAt(c).Label() for c in path.systems)
        risk = '  (%d gravity rift roll%s)' % (
            path.rifts_exited, '' if path.rifts_exited == 1 else 's') if path.rifts_exited else ''
        print('  %-6s via %s%s' % (board.SystemAt(coord).Label(), route, risk))


if __name__ == '__main__':
    sys.exit(main())
