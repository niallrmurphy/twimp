#!/usr/bin/env python3
"""Estimate the odds of an invasion taking a planet by running many simulations.

Usage:
  python3 -m twimp.simulate_invasion --ships warsun --ground infantry=3 --planet infantry=2,pds -n 10000 --seed 1

--ships are the attacker's ships in the system (only Bombardment matters,
and a war sun disables Planetary Shield). --ground is what the attacker lands.
--planet is what the defender has on the planet: ground forces and structures.
"""

import argparse
import collections
import sys

from twimp import board
from twimp import dice as dice_lib
from twimp import invasion
from twimp import simulate

ATTACKER, DEFENDER = 'attacker', 'defender'

CAPTURED = 'captured'   # the attacker took the planet
HELD = 'held'           # defending ground forces survived
WIPED = 'wiped'         # both sides' ground forces were destroyed; the defender keeps it


def ParseForces(ships, ground, planet):
    return (simulate.ParseForce(ships),
            simulate.ParseForce(ground, lambda u: u.IsGroundForce(), 'a ground force'),
            simulate.ParseForce(planet, lambda u: u.IsGroundForce() or u.IsStructure(),
                                'a ground force or structure'))


def RunOnce(ships, ground, defenders, dice):
    """Run one invasion; return (outcome, attacker ground forces left on the planet)."""
    planet = board.Planet('Target', 0, 0)
    if defenders:
        planet.controller = DEFENDER
        for unit in simulate.BuildUnits(defenders):
            planet.AddUnit(DEFENDER, unit)
    invasion.Invasion(ATTACKER, simulate.BuildUnits(ships),
                      simulate.BuildUnits(ground), [planet], dice=dice).Resolve()
    survivors = len(planet.GroundForces(ATTACKER))
    if planet.controller == ATTACKER:
        return CAPTURED, survivors
    if planet.GroundForces(DEFENDER):
        return HELD, survivors
    return WIPED, survivors


def Simulate(ships, ground, defenders, runs, seed=None):
    """Return a Counter of outcomes and the total attacker survivors over captures."""
    dice = dice_lib.Dice(seed=seed)
    outcomes = collections.Counter()
    survivors_on_capture = 0
    for _ in range(runs):
        outcome, survivors = RunOnce(ships, ground, defenders, dice)
        outcomes[outcome] += 1
        if outcome == CAPTURED:
            survivors_on_capture += survivors
    return outcomes, survivors_on_capture


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ships', default='', help='e.g. dreadnought=2,carrier')
    parser.add_argument('--ground', required=True, help='e.g. infantry=4')
    parser.add_argument('--planet', default='',
                        help='defenders, e.g. infantry=2,pds (empty: a neutral planet)')
    parser.add_argument('-n', '--runs', type=int, default=10000)
    parser.add_argument('--seed', type=int, default=None)
    args = parser.parse_args(argv)
    try:
        ships, ground, defenders = ParseForces(args.ships, args.ground, args.planet)
    except ValueError as e:
        parser.error(str(e))
    if not ground:
        parser.error('--ground needs at least one ground force')
    outcomes, survivors = Simulate(ships, ground, defenders, args.runs, args.seed)
    print("Ships:    %s" % (simulate.Describe(ships) or 'none'))
    print("Landing:  %s" % simulate.Describe(ground))
    print("Planet:   %s" % (simulate.Describe(defenders) or 'neutral, undefended'))
    print("%d invasions%s" % (args.runs,
                              '' if args.seed is None else ' (seed %d)' % args.seed))
    for label, key in (('captured', CAPTURED),
                       ('defender holds', HELD),
                       ('both wiped out', WIPED)):
        print("  %-16s %5.1f%%" % (label, 100.0 * outcomes[key] / args.runs))
    if outcomes[CAPTURED]:
        print("  %-16s %5.2f" % ('left on capture', survivors / outcomes[CAPTURED]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
