#!/usr/bin/env python3
"""Play tactical actions, with you or the computer making the choices.

Usage:
  python3 -m twimp.play_turn --human sol            # you play Sol's turn
  python3 -m twimp.play_turn --actions 6 --seed 2   # watch six computer turns
  python3 -m twimp.play_turn --load game.json --human letnev --save game.json
  python3 -m twimp.play_turn --human sol --rounds 3   # play whole rounds

Players take one tactical action each, in seat order starting with the
speaker, for --actions actions in total. With --rounds, whole rounds are
played instead: everyone acts or passes until all have passed, then the
status phase. Players not listed in --human are
played by the computer (--agent greedy or random). At each prompt, pressing
Enter accepts the suggestion shown in brackets.
"""

import argparse
import sys

from twimp import agents
from twimp import cli_agent
from twimp import dice as dice_lib
from twimp import game
from twimp import game_cli
from twimp import rounds
from twimp import tactical


def SeatOrderFromSpeaker(state):
    names = [p.name for p in state.players]
    i = names.index(state.speaker)
    return names[i:] + names[:i]


def main(argv=None, input_fn=input, print_fn=print):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--factions', default=game_cli.SAMPLE_MAP_FACTIONS,
                        help='for a new game (default: %(default)s)')
    parser.add_argument('--load', metavar='PATH', help='continue a saved game')
    parser.add_argument('--save', metavar='PATH', help='save the game afterwards')
    parser.add_argument('--human', default='',
                        help='comma-separated players you control')
    parser.add_argument('--agent', choices=('greedy', 'random'), default='greedy',
                        help='how the computer plays (default: greedy)')
    parser.add_argument('--actions', type=int, default=1,
                        help='tactical actions to play (default 1)')
    parser.add_argument('--rounds', type=int, default=None,
                        help='play this many whole rounds instead')
    parser.add_argument('--seed', type=int, default=None,
                        help='for the speaker, the dice and random agents')
    parser.add_argument('--quiet', action='store_true',
                        help="don't print the game summary at the end")
    args = parser.parse_args(argv)

    if args.load:
        state = game.Load(args.load)
    else:
        try:
            state = game.NewGame([f.strip() for f in args.factions.split(',')],
                                 game_cli.OPEN_SAMPLE_MAP
                                 if args.factions != game_cli.SAMPLE_MAP_FACTIONS
                                 else game_cli.board_lib.SAMPLE_MAP,
                                 seed=args.seed)
        except game.SetupError as e:
            parser.error(str(e))
    names = [p.name for p in state.players]
    humans = [h.strip() for h in args.human.split(',') if h.strip()]
    for h in humans:
        if h not in names:
            parser.error('%r is not playing; players are %s' % (h, ', '.join(names)))
    players = {}
    for i, name in enumerate(names):
        if name in humans:
            players[name] = cli_agent.CliAgent(name, input_fn, print_fn)
        elif args.agent == 'random':
            players[name] = agents.RandomAgent(
                seed=None if args.seed is None else args.seed * 100 + i)
        else:
            players[name] = agents.GreedyAgent()
    dice = dice_lib.Dice(seed=args.seed)

    if args.rounds:
        PlayRounds(state, players, dice, args.rounds, print_fn)
        return Finish(state, args, print_fn)

    order = SeatOrderFromSpeaker(state)
    taken = 0
    while taken < args.actions:
        able = [n for n in order if state.Player(n).tactic_tokens > 0]
        if not able:
            print_fn('Nobody has tactic tokens left.')
            break
        for name in able:
            if taken == args.actions:
                break
            report = tactical.TakeTacticalAction(state, name, players, dice)
            print_fn('')
            print_fn(tactical.DescribeReport(state, report).rstrip('\n'))
            taken += 1
    return Finish(state, args, print_fn)


def PlayRounds(state, players, dice, count, print_fn):
    def Observe(kind, player, report=None):
        print_fn('')
        if kind == rounds.PASS:
            print_fn('%s passes.' % player)
        else:
            print_fn(tactical.DescribeReport(state, report).rstrip('\n'))

    for _ in range(count):
        print_fn('')
        print_fn('=== Round %d ===' % state.round_number)
        winner = rounds.PlayRound(state, players, dice, Observe)
        if winner:
            print_fn('')
            print_fn('%s wins!' % winner)
            break


def Finish(state, args, print_fn):
    if not args.quiet:
        print_fn('')
        print_fn(state.board.Render().rstrip('\n'))
        print_fn('')
        print_fn(game.Summary(state).rstrip('\n'))
    if args.save:
        game.Save(state, args.save)
        print_fn('')
        print_fn('Saved to %s' % args.save)
    return 0


if __name__ == '__main__':
    sys.exit(main())
