#!/usr/bin/python
# Dice simulator.

import pprint
import random

class Dice(object):
    """Dice simulator, supporting potential bias."""
    @staticmethod
    def RollWithTarget(target_number,
                       number_of_dice,
                       sides=10,
                       alteration=None,
                       verbosity=False):
        """Roll number_of_dice and report those exceeding target_number."""
        target_exceeded = 0
        for x in range(0, number_of_dice):
            y = random.randint(1, sides)
            # Intended for lambdas (e.g. a constant +1, or equivalent)
            if verbosity: print ("NOTE: rolled ", y)
            if alteration:
                y = alteration(y)
                print ("NOTE: alteration called, changed to ", y)
            if y >= target_number:
                if verbosity: print (">= Target")
                target_exceeded += 1
        return target_exceeded
