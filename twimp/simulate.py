#!/usr/bin/env python3
"""Estimate space combat odds by running many simulated combats.

Usage:
  python3 -m twimp.simulate dreadnought=2,fighter=3,carrier destroyer=6 -n 10000 --seed 1
"""

import argparse
import collections
import sys

from twimp import combat
from twimp import dice as dice_lib
from twimp.units import Unit, UnitType


def ParseForce(spec, allowed=Unit.IsShip, kind='a ship'):
    """Parse 'dreadnought=2,carrier' into {UnitType.DREADNOUGHT: 2, UnitType.CARRIER: 1}.

    allowed is a predicate on a Unit; units that fail it are rejected as not
    being `kind`.
    """
    force = collections.OrderedDict()
    for part in spec.split(','):
        part = part.strip()
        if not part:
            continue
        name, _, count = part.partition('=')
        key = name.strip().upper().replace('_', '').replace(' ', '')
        try:
            unit_type = UnitType[key]
        except KeyError:
            raise ValueError("Unknown unit %r; choose from %s" % (
                name, ', '.join(t.name.lower() for t in UnitType)))
        if not allowed(Unit(unit_type)):
            raise ValueError("%s is not %s" % (unit_type.name.lower(), kind))
        force[unit_type] = force.get(unit_type, 0) + (int(count) if count else 1)
    return force


def BuildUnits(force):
    return [Unit(t) for t, n in force.items() for _ in range(n)]


def Simulate(attacker, defender, runs, seed=None):
    """Run `runs` combats; return a Counter of outcomes and the total rounds."""
    dice = dice_lib.Dice(seed=seed)
    outcomes = collections.Counter()
    total_rounds = 0
    for _ in range(runs):
        result = combat.SpaceCombat(BuildUnits(attacker), BuildUnits(defender),
                                    dice=dice).Resolve()
        outcomes[result.winner] += 1
        total_rounds += len(result.rounds)
    return outcomes, total_rounds


def Describe(force):
    return ', '.join('%d %s' % (n, t.name.lower()) for t, n in force.items())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('attacker', help='e.g. dreadnought=2,carrier,fighter=3')
    parser.add_argument('defender', help='e.g. destroyer=6')
    parser.add_argument('-n', '--runs', type=int, default=10000)
    parser.add_argument('--seed', type=int, default=None)
    args = parser.parse_args(argv)
    try:
        attacker = ParseForce(args.attacker)
        defender = ParseForce(args.defender)
    except ValueError as e:
        parser.error(str(e))
    outcomes, total_rounds = Simulate(attacker, defender, args.runs, args.seed)
    print("Attacker: %s" % Describe(attacker))
    print("Defender: %s" % Describe(defender))
    print("%d combats%s" % (args.runs,
                            '' if args.seed is None else ' (seed %d)' % args.seed))
    for label, key in (('attacker wins', combat.ATTACKER),
                       ('defender wins', combat.DEFENDER),
                       ('draw', None)):
        print("  %-14s %5.1f%%" % (label, 100.0 * outcomes[key] / args.runs))
    print("  %-14s %5.2f" % ('average rounds', total_rounds / args.runs))
    return 0


if __name__ == '__main__':
    sys.exit(main())
