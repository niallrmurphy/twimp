#!/usr/bin/env python3
"""Serve twimp games to web browsers.

Usage:
  python3 -m twimp.server                  # http://127.0.0.1:8000
  python3 -m twimp.server --host 0.0.0.0   # let others on your network join

Open the page, choose factions and which seats people will play, and the
page gives a link per human seat. Everyone opens their link; the computer
plays the remaining seats.

Each game's engine runs in its own thread. When it needs a person's
decision it waits; the browser polls for the game state, sees the decision,
and posts an answer, which wakes the engine. A single lock per game keeps
the engine and the web requests from touching the game state at once.
"""

import argparse
import http.server
import json
import os
import secrets
import sys
import threading
import traceback
import urllib.parse

from twimp import agents
from twimp import board as board_lib
from twimp import combat
from twimp import decisions
from twimp import dice as dice_lib
from twimp import game
from twimp import game_cli
from twimp import rounds
from twimp import tactical
from twimp.decisions import Key

WEB_DIR = os.path.join(os.path.dirname(__file__), 'web')
COLORS = ['#d7263d', '#1b998b', '#2e86de', '#f46036', '#8e44ad', '#e2b714',
          '#e84393', '#6ab04c']
NARRATIVE_LIMIT = 400
BATTLES_SHOWN = 30


class WebAgent(decisions.DecisionAgent):
    """A seat played from a browser: Ask() waits until the answer arrives."""
    def __init__(self, name, session):
        super(WebAgent, self).__init__(name)
        self.session = session

    def Ask(self, decision):
        return self.session.WaitForAnswer(decision)


class Session(object):
    """One game: its state, players, engine thread and pending decision."""

    def __init__(self, game_id, state, humans, computer='greedy', rounds_to_play=5,
                 seed=None, delay=0.4):
        self.id = game_id
        self.state = state
        self.cond = threading.Condition()
        self.tokens = {name: secrets.token_urlsafe(12) for name in humans}
        self.colors = {p.name: COLORS[i % len(COLORS)] for i, p in enumerate(state.players)}
        self.agents = {}
        for i, p in enumerate(state.players):
            if p.name in humans:
                self.agents[p.name] = WebAgent(p.name, self)
            elif computer == 'random':
                self.agents[p.name] = agents.RandomAgent(
                    seed=None if seed is None else seed * 100 + i)
            else:
                self.agents[p.name] = agents.GreedyAgent()
        self.dice = dice_lib.Dice(seed=seed)
        self.rounds_to_play = rounds_to_play
        self.delay = delay
        self.pending = None        # the Decision being waited on
        self.answer = None
        self.next_decision_id = 1
        self.narrative = []
        self.entries = 0           # numbered log entries so far
        self.battles = []          # every combat, as it happens
        self.status = 'running'    # running, finished or error
        self.error = None
        self.version = 0           # bumps whenever anything changes
        self.thread = threading.Thread(target=self._Run, daemon=True)

    def Start(self):
        self.thread.start()

    # The engine side (runs in self.thread, holding self.cond).

    def _Changed(self):
        self.version += 1
        self.cond.notify_all()

    def _Say(self, text):
        """Add a numbered entry to the game log. Numbers only ever go up,
        so players can refer to "entry 57"."""
        self.entries += 1
        lines = text.rstrip('\n').split('\n')
        self.narrative.append('#%d %s' % (self.entries, lines[0]))
        self.narrative.extend(lines[1:])
        del self.narrative[:-NARRATIVE_LIMIT]
        self._Changed()

    def _Observe(self, kind, player, report=None):
        if kind == rounds.PASS:
            self._Say('%s passes.' % player)
        else:
            self._Say(tactical.DescribeReport(self.state, report))
        # Give browsers a moment to show what just happened.
        if self.delay:
            self.cond.wait(self.delay)

    def _Combat(self, event, kind, system, attacker, defender, attacker_units,
                defender_units, planet=None, report=None, result=None):
        """Keep a running record of each combat for the browsers' overlay."""
        describe = game.DescribeUnits
        if event == 'start':
            self.battles.append({
                'id': len(self.battles) + 1, 'kind': kind, 'system': system,
                'planet': planet, 'attacker': attacker, 'defender': defender,
                'status': 'fighting', 'round': 0,
                'before': [describe(attacker_units), describe(defender_units)],
                'now': [describe(attacker_units), describe(defender_units)],
                'rounds': [], 'rolling': None, 'winner': None, 'retreated': None})
            self._Changed()
            return
        battle = self.battles[-1]
        battle['now'] = [describe(attacker_units), describe(defender_units)]
        if event == 'rolled':
            battle['rolling'] = {'round': report.round_number,
                                 'afb': [report.attacker_afb_hits, report.defender_afb_hits],
                                 'hits': [report.attacker_hits, report.defender_hits]}
        elif event == 'round':
            battle['rolling'] = None
            battle['round'] = report.round_number
            battle['rounds'].append({
                'round': report.round_number,
                'afb': [report.attacker_afb_hits, report.defender_afb_hits],
                'hits': [report.attacker_hits, report.defender_hits],
                'losses': [describe(report.attacker_losses), describe(report.defender_losses)],
                'retreat': {combat.ATTACKER: attacker,
                            combat.DEFENDER: defender}.get(report.retreat),
            })
        elif event == 'end':
            names = {combat.ATTACKER: attacker, combat.DEFENDER: defender}
            battle['status'] = 'over'
            battle['winner'] = names.get(result.winner)
            battle['retreated'] = names.get(result.retreated)
        self._Changed()
        # Pause so people can watch the fight unfold.
        if self.delay:
            self.cond.wait(self.delay * 2)

    def _Run(self):
        with self.cond:
            try:
                for _ in range(self.rounds_to_play):
                    self._Say('=== Round %d ===' % self.state.round_number)
                    winner = rounds.PlayRound(self.state, self.agents, self.dice,
                                              self._Observe, self._Combat)
                    if winner:
                        self._Say('%s wins!' % winner)
                        break
                self._Say('Game over.')
                self.status = 'finished'
            except Exception as e:
                traceback.print_exc()
                self.status = 'error'
                self.error = '%s: %s' % (type(e).__name__, e)
                self._Say('The game stopped with an error: %s' % self.error)
            self.pending = None
            self._Changed()

    def WaitForAnswer(self, decision):
        """Called by a WebAgent in the engine thread (which holds self.cond)."""
        decision.id = self.next_decision_id
        self.next_decision_id += 1
        self.pending, self.answer = decision, None
        self._Changed()
        while self.answer is None:
            self.cond.wait()
        result, self.pending, self.answer = self.answer[0], None, None
        self._Changed()
        return result

    # The web side (runs in request threads).

    def SeatFor(self, token):
        for name, t in self.tokens.items():
            if token and secrets.compare_digest(t, token):
                return name
        return None

    def Answer(self, token, decision_id, answer):
        """Returns None if accepted, or an error message."""
        with self.cond:
            seat = self.SeatFor(token)
            if seat is None:
                return 'Not a player in this game'
            if self.pending is None or self.pending.player != seat:
                return 'Nothing to answer right now'
            if self.pending.id != decision_id:
                return 'That question has already been answered'
            try:
                result = self.pending.parse(answer)
            except ValueError as e:
                return str(e)
            self.answer = (result,)
            self.cond.notify_all()
            return None

    def View(self, token):
        """Everything a browser needs to draw the game, as JSON."""
        with self.cond:
            seat = self.SeatFor(token)
            pending = None
            if self.pending is not None:
                pending = {'player': self.pending.player}
                if self.pending.player == seat:
                    pending = self.pending.ToJson()
            return {
                'id': self.id, 'version': self.version, 'status': self.status,
                'error': self.error, 'seat': seat,
                'round': self.state.round_number, 'phase': self.state.phase,
                'speaker': self.state.speaker, 'custodians': self.state.custodians,
                'winner': self.state.Winner(),
                'players': [self._PlayerView(p) for p in self.state.players],
                'board': _BoardView(self.state),
                'pending': pending,
                'battles': self.battles[-BATTLES_SHOWN:],
                'narrative': self.narrative[-200:],
            }

    def _PlayerView(self, p):
        planets = p.ControlledPlanets(self.state.board)
        ready = [pl for pl in planets if not pl.exhausted]
        return {
            'name': p.name, 'faction': p.faction_data['name'], 'color': self.colors[p.name],
            'human': p.name in self.tokens, 'victory_points': p.victory_points,
            'tactic': p.tactic_tokens, 'fleet': p.fleet_tokens, 'strategy': p.strategy_tokens,
            'trade_goods': p.trade_goods, 'commodities': p.commodities,
            'max_commodities': p.max_commodities, 'technologies': p.technologies,
            'planets': len(planets),
            'resources': [sum(pl.resources for pl in ready), sum(pl.resources for pl in planets)],
            'influence': [sum(pl.influence for pl in ready), sum(pl.influence for pl in planets)],
            'passed': p.name in self.state.passed,
            'home': Key(self.state.HomeSystem(p.name)),
        }


def _UnitCounts(units):
    counts = {}
    for u in units:
        name = u.unit_type.name.lower()
        counts[name] = counts.get(name, 0) + 1
        if u.damaged:
            counts[name + '_damaged'] = counts.get(name + '_damaged', 0) + 1
    return counts


def _BoardView(state):
    systems = []
    for coord, system in state.board.systems.items():
        systems.append({
            'key': Key(coord), 'q': coord.q, 'r': coord.r,
            'tile': system.tile_id, 'label': system.Label(),
            'anomaly': system.anomaly.value if system.anomaly else None,
            'wormholes': sorted(system.wormholes), 'home': system.home,
            'command_tokens': sorted(system.command_tokens),
            'space': {p: _UnitCounts(us) for p, us in system.space.items() if us},
            'planets': [{'name': p.name, 'resources': p.resources, 'influence': p.influence,
                         'trait': p.trait, 'specialty': p.tech_specialty,
                         'controller': p.controller, 'exhausted': p.exhausted,
                         'units': {pl: _UnitCounts(us) for pl, us in p.units.items() if us}}
                        for p in system.planets],
        })
    return {'systems': systems}


class Server(object):
    """All the games this process is running."""

    def __init__(self, delay=0.4):
        self.games = {}
        self.lock = threading.Lock()
        self.delay = delay

    def Create(self, request):
        factions = request.get('factions') or game_cli.SAMPLE_MAP_FACTIONS.split(',')
        humans = request.get('humans') or []
        if not isinstance(factions, list) or not isinstance(humans, list):
            raise ValueError('factions and humans must be lists')
        for h in humans:
            if h not in factions:
                raise ValueError('%r is not one of the factions' % h)
        on_sample = sorted(factions) == sorted(game_cli.SAMPLE_MAP_FACTIONS.split(','))
        map_string = request.get('map') or (
            board_lib.SAMPLE_MAP if on_sample else game_cli.OPEN_SAMPLE_MAP)
        if not isinstance(map_string, str):
            raise ValueError('map must be a map string')
        seed = request.get('seed')
        if seed is not None and not isinstance(seed, int):
            raise ValueError('seed must be a whole number')
        rounds_to_play = request.get('rounds', 5)
        if not isinstance(rounds_to_play, int) or not 1 <= rounds_to_play <= 20:
            raise ValueError('rounds must be from 1 to 20')
        computer = request.get('computer', 'greedy')
        if computer not in ('greedy', 'random'):
            raise ValueError('computer must be greedy or random')
        try:
            state = game.NewGame(factions, map_string, speaker=request.get('speaker'),
                                 seed=seed)
        except (game.SetupError, board_lib.CannotPerformException) as e:
            raise ValueError(str(e))
        with self.lock:
            game_id = secrets.token_urlsafe(6)
            session = Session(game_id, state, humans, computer, rounds_to_play, seed,
                              self.delay)
            self.games[game_id] = session
        session.Start()
        return {'game': game_id, 'seats': session.tokens}

    def Get(self, game_id):
        with self.lock:
            return self.games.get(game_id)

    def List(self):
        with self.lock:
            return [{'game': g.id, 'players': [p.name for p in g.state.players],
                     'humans': sorted(g.tokens), 'status': g.status,
                     'round': g.state.round_number} for g in self.games.values()]


def MakeHandler(server):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass   # keep the terminal quiet; errors still go to stderr

        def _Send(self, code, body, content_type='application/json'):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def _Static(self, name, content_type):
            with open(os.path.join(WEB_DIR, name), 'rb') as f:
                self._Send(200, f.read(), content_type)

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(url.query)
            parts = [p for p in url.path.split('/') if p]
            if url.path == '/':
                return self._Static('index.html', 'text/html; charset=utf-8')
            if url.path == '/app.js':
                return self._Static('app.js', 'text/javascript; charset=utf-8')
            if url.path == '/style.css':
                return self._Static('style.css', 'text/css; charset=utf-8')
            if parts == ['api', 'factions']:
                return self._Send(200, [{'key': k, 'name': v['name']}
                                        for k, v in sorted(game.FactionData().items())])
            if parts == ['api', 'games']:
                return self._Send(200, server.List())
            if len(parts) in (3, 4) and parts[:2] == ['api', 'games']:
                session = server.Get(parts[2])
                if session is None:
                    return self._Send(404, {'error': 'No such game'})
                token = (query.get('seat') or [None])[0]
                if len(parts) == 3:
                    known = (query.get('version') or [None])[0]
                    if known is not None and known == str(session.version):
                        return self._Send(200, {'unchanged': True, 'version': session.version})
                    return self._Send(200, session.View(token))
                if parts[3] == 'save':
                    with session.cond:
                        return self._Send(200, game.ToDict(session.state))
            self._Send(404, {'error': 'Not found'})

        def do_POST(self):
            parts = [p for p in urllib.parse.urlparse(self.path).path.split('/') if p]
            try:
                length = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(length) or b'{}')
            except ValueError:
                return self._Send(400, {'error': 'Bad JSON'})
            if parts == ['api', 'games']:
                try:
                    return self._Send(200, server.Create(body))
                except ValueError as e:
                    return self._Send(400, {'error': str(e)})
            if len(parts) == 4 and parts[:2] == ['api', 'games'] and parts[3] == 'answer':
                session = server.Get(parts[2])
                if session is None:
                    return self._Send(404, {'error': 'No such game'})
                error = session.Answer(body.get('seat'), body.get('id'), body.get('answer'))
                if error:
                    return self._Send(400, {'error': error})
                return self._Send(200, {'ok': True})
            self._Send(404, {'error': 'Not found'})

    return Handler


def Serve(host='127.0.0.1', port=8000, delay=0.4):
    """Start serving; returns the HTTP server (call serve_forever on it)."""
    games = Server(delay)
    httpd = http.server.ThreadingHTTPServer((host, port), MakeHandler(games))
    httpd.daemon_threads = True
    httpd.games = games
    return httpd


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--host', default='127.0.0.1',
                        help='use 0.0.0.0 to let other machines connect')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--delay', type=float, default=0.4,
                        help='seconds to pause after each turn, so people can follow')
    args = parser.parse_args(argv)
    httpd = Serve(args.host, args.port, args.delay)
    print('twimp is running at http://%s:%d/' % (
        'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host, args.port))
    if args.host == '0.0.0.0':
        print('Other players can use your machine\'s network address instead of localhost.')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
