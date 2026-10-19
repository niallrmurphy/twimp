#!/usr/bin/env python3
"""Set up, save and inspect games.

Usage:
  python3 -m twimp.game_cli new                       # the sample map's six factions
  python3 -m twimp.game_cli new --factions sol,hacan,naalu --seed 3 --save game.json
  python3 -m twimp.game_cli show game.json
  python3 -m twimp.game_cli factions                  # list available factions

A new game is printed (and saved with --save). Home systems already on the
map are used; others go in empty outer-ring slots, so with a map that has
0 at the home positions any factions can be used.
"""

import argparse
import sys

from twimp import board as board_lib
from twimp import game

SAMPLE_MAP_FACTIONS = 'sol,letnev,jolnar,sardakk,xxcha,yssaril'

# The sample map with its six home systems replaced by empty slots.
OPEN_SAMPLE_MAP = ' '.join(
    '0' if board_lib.TileData()[t].get('home') else t
    for t in board_lib.SAMPLE_MAP.split())


def Show(state, show_map=True):
    if show_map:
        print(state.board.Render(), end='')
        print()
    print(game.Summary(state), end='')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)
    new = commands.add_parser('new', help='set up a new game')
    new.add_argument('--factions', default=SAMPLE_MAP_FACTIONS,
                     help='comma-separated, in seat order (default: %(default)s)')
    new.add_argument('--map', default=None,
                     help='map string (default: the sample map, with home slots '
                          'opened up if other factions are chosen)')
    new.add_argument('--speaker', default=None, help='default: chosen at random')
    new.add_argument('--seed', type=int, default=None)
    new.add_argument('--save', metavar='PATH', help='save the game as JSON')
    new.add_argument('--no-map', action='store_true', help="don't draw the map")
    show = commands.add_parser('show', help='print a saved game')
    show.add_argument('path')
    show.add_argument('--no-map', action='store_true', help="don't draw the map")
    commands.add_parser('factions', help='list available factions')
    args = parser.parse_args(argv)

    if args.command == 'factions':
        for key, data in sorted(game.FactionData().items()):
            print('  %-8s %s (home system %s)' % (key, data['name'], data['home_system']))
        return 0
    if args.command == 'show':
        Show(game.Load(args.path), not args.no_map)
        return 0
    factions = [f.strip() for f in args.factions.split(',') if f.strip()]
    map_string = args.map
    if map_string is None:
        map_string = (board_lib.SAMPLE_MAP if args.factions == SAMPLE_MAP_FACTIONS
                      else OPEN_SAMPLE_MAP)
    try:
        state = game.NewGame(factions, map_string, speaker=args.speaker, seed=args.seed)
    except (game.SetupError, board_lib.CannotPerformException) as e:
        parser.error(str(e))
    Show(state, not args.no_map)
    if args.save:
        game.Save(state, args.save)
        print('\nSaved to %s' % args.save)
    return 0


if __name__ == '__main__':
    sys.exit(main())
