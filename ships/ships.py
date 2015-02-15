#!/usr/bin/python

class CannotPerformException(Exception):
  pass


class SpaceVehicle(object):
  """Describes the abstract interface; not meant to actually do anything."""
  def __init__():
    pass

  def CostToBuild():
    pass

  def MoveTo():
    pass

  def WhereCanIMoveTo():
    pass

  def _ComputeMoveFeasibility():
    pass

  def ShootAt():
    pass

  def WhatCanIShootAt():
    pass

  def _SelectableTargets():
    pass


class SpaceDock(SpaceVehicle):
  """A space dock orbits around a planet and builds new space vehicles."""
  def Build():
    pass

  def CanBuild():
    pass

  def Blockade():
    pass

  def AmIBlockaded():
    pass


class Fighter(SpaceVehicle):
  """A cheap, inefficient shooter - but excellent damage soaker."""
  pass
