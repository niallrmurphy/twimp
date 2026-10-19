#!/usr/bin/env python3
# Game rounds: the action phase and a cut-down status phase.
#
# Until strategy cards exist (stage 7) there's no strategy phase, and the
# initiative order is the seat order starting with the speaker. The status
# phase does what it can without objectives, action cards or strategy cards:
#
#   - remove each player's command tokens from the board;
#   - each player gains 2 command tokens (if they have them in
#     reinforcements) and may redistribute all of them among their pools;
#   - ready every planet;
#   - repair every damaged unit.
#
# The agenda phase needs agenda cards, so it's skipped even once the
# custodians token is gone.

from twimp import agents as agents_lib
from twimp import game as game_lib
from twimp import limits
from twimp import tactical

TACTICAL, PASS = 'tactical', 'pass'
COMMAND_TOKENS_GAINED = 2


class GameOver(Exception):
    pass


def _Agents(state, agents):
    agents = dict(agents or {})
    for p in state.players:
        agents.setdefault(p.name, agents_lib.GreedyAgent())
    return agents


def ActionOptions(state, player):
    options = [TACTICAL] if state.Player(player).tactic_tokens > 0 else []
    return options + [PASS]


def NextToAct(state, after=None):
    """Who acts next in the action phase: the first player (in initiative
    order, starting after `after`) who hasn't passed. None if all have."""
    order = state.SeatOrderFromSpeaker()
    if after is not None:
        i = order.index(after) + 1
        order = order[i:] + order[:i]
    for name in order:
        if name not in state.passed:
            return name
    return None


def PlayActionPhase(state, agents=None, dice=None, observer=None, listener=None):
    """Players take turns until everyone has passed.

    observer, if given, is called as observer(kind, **details) after each
    turn: ('tactical', player=, report=) or ('pass', player=). listener
    follows combats as they happen (see tactical.TakeTacticalAction).
    Returns the winner's name if someone reached the target, else None.
    """
    agents = _Agents(state, agents)
    if state.phase != game_lib.ACTION:
        state.phase = game_lib.ACTION
        state.passed = set()
        state.Log('phase_started', phase=game_lib.ACTION)
    player = NextToAct(state)
    while player is not None:
        options = ActionOptions(state, player)
        choice = agents[player].ChooseAction(state, player, list(options))
        if choice not in options:
            raise tactical.IllegalAction("%s can't choose %r" % (player, choice))
        if choice == PASS:
            state.passed.add(player)
            state.Log('passed', player=player)
            if observer:
                observer(PASS, player=player)
        else:
            report = tactical.TakeTacticalAction(state, player, agents, dice, listener)
            if observer:
                observer(TACTICAL, player=player, report=report)
            if state.Winner():
                state.Log('game_won', player=state.Winner())
                return state.Winner()
        player = NextToAct(state, after=player)
    return None


def PlayStatusPhase(state, agents=None):
    agents = _Agents(state, agents)
    state.phase = game_lib.STATUS
    state.Log('phase_started', phase=game_lib.STATUS)
    for system in state.board.systems.values():
        system.command_tokens.clear()
    for name in state.SeatOrderFromSpeaker():
        player = state.Player(name)
        gained = min(COMMAND_TOKENS_GAINED, state.ReinforcementTokens(name))
        total = player.tactic_tokens + player.fleet_tokens + player.strategy_tokens + gained
        split = agents[name].ChooseCommandTokens(state, name, total)
        if (len(split) != 3 or any(not isinstance(n, int) or n < 0 for n in split)
                or sum(split) != total):
            raise tactical.IllegalAction(
                "%s must split %d command tokens into three pools, not %r" % (
                    name, total, split))
        player.tactic_tokens, player.fleet_tokens, player.strategy_tokens = split
        state.Log('command_tokens', player=name, gained=gained,
                  tactic=split[0], fleet=split[1], strategy=split[2])
        # A smaller fleet pool may leave too many ships somewhere.
        for coord in list(state.board.systems):
            limits.EnforceFleetPool(state, coord, name, agents[name])
    for system in state.board.systems.values():
        for planet in system.planets:
            planet.exhausted = False
        for units in list(system.space.values()) + [
                u for p in system.planets for u in p.units.values()]:
            for unit in units:
                unit.Repair()
    state.passed = set()


def PlayRound(state, agents=None, dice=None, observer=None, listener=None):
    """Play one round. Returns the winner's name if the game ended."""
    agents = _Agents(state, agents)
    state.Log('round_started', round=state.round_number)
    if state.phase == game_lib.STRATEGY:
        state.Log('phase_skipped', phase=game_lib.STRATEGY,
                  reason='no strategy cards yet')
    winner = PlayActionPhase(state, agents, dice, observer, listener)
    if winner:
        return winner
    PlayStatusPhase(state, agents)
    if not state.custodians:
        state.Log('phase_skipped', phase=game_lib.AGENDA, reason='no agenda cards yet')
    state.round_number += 1
    state.phase = game_lib.STRATEGY
    return None
