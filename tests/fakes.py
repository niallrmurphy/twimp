#!/usr/bin/env python3
# Test doubles.

from twimp import dice


class ScriptedDice(dice.Dice):
    """Dice that return a fixed sequence of rolls, for exact scenario tests."""
    def __init__(self, rolls):
        super(ScriptedDice, self).__init__(seed=0)
        self.rolls = list(rolls)

    def Roll(self, sides=10):
        if not self.rolls:
            raise AssertionError("ScriptedDice ran out of rolls")
        return self.rolls.pop(0)
