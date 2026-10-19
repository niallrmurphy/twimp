#!/usr/bin/env python3
# Dice simulator.

import random


class Dice(object):
    """Dice simulator, supporting potential bias.

    Holds its own random number generator so that games and tests can be made
    reproducible by passing a seed (or a pre-built random.Random).
    """
    def __init__(self, seed=None, rng=None):
        if rng is not None:
            self.rng = rng
        else:
            self.rng = random.Random(seed)

    def Roll(self, sides=10):
        return self.rng.randint(1, sides)

    def RollWithTarget(self,
                       target_number,
                       number_of_dice,
                       sides=10,
                       alteration=None,
                       verbosity=False):
        """Roll number_of_dice and report those meeting or exceeding target_number."""
        target_exceeded = 0
        for x in range(0, number_of_dice):
            y = self.Roll(sides)
            if verbosity: print ("NOTE: rolled ", y)
            # Intended for lambdas (e.g. a constant +1, or equivalent)
            if alteration:
                y = alteration(y)
                if verbosity: print ("NOTE: alteration called, changed to ", y)
            if y >= target_number:
                if verbosity: print (">= Target")
                target_exceeded += 1
        return target_exceeded
