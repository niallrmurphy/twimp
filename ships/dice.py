#!/usr/bin/python
# Dice simulator.

from __future__ import print_function

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
    target_exceeded = 0
    for x in range(0, number_of_dice):
      y = random.randint(1, sides)
      # Intended for lambdas (e.g. a constant +1, or equivalent)
      print ("NOTE: rolled ", y) if verbosity else None
      if alteration:
        y = alteration(y)
        print ("NOTE: alteration called, changed to ", y)
      if y >= target_number:
        print (">= Target") if verbosity else None
        target_exceeded += 1
    return target_exceeded
