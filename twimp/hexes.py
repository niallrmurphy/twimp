#!/usr/bin/env python3
# Hex grid geometry for the TI4 board.
#
# TI4 tiles are flat-topped hexes, so every system has neighbours directly
# north and south. We use axial coordinates (q, r): q increases to the east
# (south-east), r increases to the south. Mecatol Rex is at (0, 0).

import collections

Hex = collections.namedtuple('Hex', ['q', 'r'])

CENTER = Hex(0, 0)

NORTH = Hex(0, -1)
NORTH_EAST = Hex(1, -1)
SOUTH_EAST = Hex(1, 0)
SOUTH = Hex(0, 1)
SOUTH_WEST = Hex(-1, 1)
NORTH_WEST = Hex(-1, 0)

# Clockwise from north.
DIRECTIONS = [NORTH, NORTH_EAST, SOUTH_EAST, SOUTH, SOUTH_WEST, NORTH_WEST]


def Add(a, b):
    return Hex(a.q + b.q, a.r + b.r)


def Scale(a, k):
    return Hex(a.q * k, a.r * k)


def Neighbors(h):
    """The six physically adjacent hexes, clockwise from north."""
    return [Add(h, d) for d in DIRECTIONS]


def Distance(a, b):
    dq, dr = a.q - b.q, a.r - b.r
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


def Ring(radius, center=CENTER):
    """The hexes at `radius` from center, clockwise starting from due north.

    This is the order map strings use: ring 1 starts with the tile directly
    above Mecatol Rex and runs clockwise.
    """
    if radius == 0:
        return [center]
    results = []
    h = Add(center, Scale(NORTH, radius))
    # Walking clockwise from the northernmost hex: first south-east, etc.
    for direction in (SOUTH_EAST, SOUTH, SOUTH_WEST, NORTH_WEST, NORTH, NORTH_EAST):
        for _ in range(radius):
            results.append(h)
            h = Add(h, direction)
    return results


def Spiral(radius, center=CENTER):
    """Every hex out to `radius`, ring by ring, in map-string order."""
    results = []
    for k in range(radius + 1):
        results.extend(Ring(k, center))
    return results
