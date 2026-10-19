#!/usr/bin/env python3

import json
import threading
import time
import unittest
import urllib.error
import urllib.request

from twimp import server


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.Serve('127.0.0.1', 0, delay=0)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = 'http://127.0.0.1:%d' % cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def Call(self, path, body=None, raw=False):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data,
                                         headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                content = response.read()
                return response.status, content if raw else json.loads(content)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def WaitFor(self, game, token, predicate, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            _, view = self.Call('/api/games/%s?seat=%s' % (game, token))
            if predicate(view):
                return view
            time.sleep(0.02)
        self.fail('timed out waiting')

    def Create(self, **request):
        request.setdefault('seed', 1)
        code, created = self.Call('/api/games', request)
        self.assertEqual(code, 200, created)
        return created


class TestApi(ServerTest):
    def testStaticFiles(self):
        for path, needle in (('/', b'<title>twimp</title>'), ('/app.js', b'function Lobby'),
                             ('/style.css', b':root')):
            code, body = self.Call(path, raw=True)
            self.assertEqual(code, 200)
            self.assertIn(needle, body)

    def testFactions(self):
        code, factions = self.Call('/api/factions')
        self.assertEqual(code, 200)
        self.assertIn('sol', [f['key'] for f in factions])

    def testCreateErrors(self):
        for body in ({'factions': ['sol']}, {'factions': ['sol', 'saar']},
                     {'factions': ['sol', 'letnev'], 'humans': ['xxcha']},
                     {'factions': ['sol', 'letnev'], 'rounds': 0},
                     {'factions': ['sol', 'letnev'], 'computer': 'clever'},
                     {'factions': 'sol'}):
            code, result = self.Call('/api/games', body)
            self.assertEqual(code, 400, body)
            self.assertIn('error', result)

    def testComputerOnlyGameFinishes(self):
        created = self.Create(factions=['sol', 'letnev', 'hacan'], rounds=2)
        view = self.WaitFor(created['game'], '', lambda v: v['status'] != 'running')
        self.assertEqual(view['status'], 'finished')
        self.assertEqual(view['round'], 3)
        entries = [line for line in view['narrative'] if line.startswith('#')]
        self.assertTrue(entries[-1].endswith(' Game over.'))
        numbers = [int(line[1:].split()[0]) for line in entries]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))
        self.assertIsNone(view['seat'])
        code, saved = self.Call('/api/games/%s/save' % created['game'])
        self.assertEqual(saved['round'], 3)
        code, games = self.Call('/api/games')
        self.assertIn(created['game'], [g['game'] for g in games])

    def testBattlesAreRecorded(self):
        created = self.Create(factions=['sol', 'letnev'], map='{18} 1 26 10 46 47 48',
                              computer='random', rounds=6, seed=3)
        view = self.WaitFor(created['game'], '', lambda v: v['status'] != 'running')
        self.assertTrue(view['battles'], 'expected the random players to fight')
        for battle in view['battles']:
            self.assertEqual(battle['status'], 'over')
            self.assertIsNone(battle['rolling'])
            self.assertIn(battle['kind'], ('space', 'ground'))
            self.assertEqual({battle['attacker'], battle['defender']}, {'sol', 'letnev'})
            self.assertEqual([r['round'] for r in battle['rounds']],
                             list(range(1, len(battle['rounds']) + 1)))
        self.assertEqual([b['id'] for b in view['battles']],
                         list(range(1, len(view['battles']) + 1)))

    def testBadMap(self):
        code, result = self.Call('/api/games', {'factions': ['sol', 'letnev'],
                                                'map': '19 26 83A2'})
        self.assertEqual(code, 400)
        self.assertIn('Unknown tile', result['error'])

    def testUnknownGame(self):
        self.assertEqual(self.Call('/api/games/nope')[0], 404)
        self.assertEqual(self.Call('/api/games/nope/answer', {})[0], 404)


class TestTwoBrowsers(ServerTest):
    def testTwoHumanSeats(self):
        created = self.Create(factions=['sol', 'letnev', 'jolnar'],
                              humans=['sol', 'letnev'], rounds=1)
        game, seats = created['game'], created['seats']
        self.assertEqual(sorted(seats), ['letnev', 'sol'])

        # Someone gets asked something. Only they see the question; the
        # other seat (and spectators) only see who's deciding.
        view = self.WaitFor(game, seats['sol'], lambda v: v['pending'] is not None)
        asked = view['pending']['player']
        other = 'letnev' if asked == 'sol' else 'sol'
        mine = self.Call('/api/games/%s?seat=%s' % (game, seats[asked]))[1]['pending']
        theirs = self.Call('/api/games/%s?seat=%s' % (game, seats[other]))[1]['pending']
        spectator = self.Call('/api/games/%s' % game)[1]['pending']
        self.assertEqual(mine['kind'], 'action')
        self.assertEqual(theirs, {'player': asked})
        self.assertEqual(spectator, {'player': asked})

        # The wrong seat, a stale id, and a bad answer are all refused.
        answer = '/api/games/%s/answer' % game
        self.assertEqual(self.Call(answer, {'seat': seats[other], 'id': mine['id'],
                                            'answer': 'pass'})[0], 400)
        self.assertEqual(self.Call(answer, {'seat': seats[asked], 'id': mine['id'] + 7,
                                            'answer': 'pass'})[0], 400)
        code, result = self.Call(answer, {'seat': seats[asked], 'id': mine['id'],
                                          'answer': 'dance'})
        self.assertEqual(code, 400)
        self.assertIn('Choose one of', result['error'])

        # Answering every question with its default plays the round out.
        answered = 0
        deadline = time.time() + 20
        while time.time() < deadline:
            view = self.Call('/api/games/%s' % game)[1]
            if view['status'] != 'running':
                break
            pending = view['pending']
            if pending:
                token = seats[pending['player']]
                question = self.Call('/api/games/%s?seat=%s' % (game, token))[1]['pending']
                if question and 'kind' in question:
                    code, _ = self.Call(answer, {'seat': token, 'id': question['id'],
                                                 'answer': question['default']})
                    self.assertEqual(code, 200)
                    answered += 1
                    continue
            time.sleep(0.01)
        self.assertEqual(view['status'], 'finished')
        self.assertGreater(answered, 4)

    def testUnchangedViewsAreSmall(self):
        created = self.Create(factions=['sol', 'letnev'], humans=['sol'], rounds=1)
        view = self.WaitFor(created['game'], created['seats']['sol'],
                            lambda v: v['pending'] is not None)
        code, again = self.Call('/api/games/%s?seat=%s&version=%d' % (
            created['game'], created['seats']['sol'], view['version']))
        self.assertEqual(again, {'unchanged': True, 'version': view['version']})


if __name__ == '__main__':
    unittest.main()
