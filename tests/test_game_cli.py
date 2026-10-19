#!/usr/bin/env python3

import contextlib
import io
import os
import tempfile
import unittest

from twimp import game_cli


def Run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        game_cli.main(list(argv))
    return out.getvalue()


class TestGameCli(unittest.TestCase):
    def testNewDefault(self):
        text = Run('new', '--seed', '1')
        self.assertIn('13H', text)
        self.assertIn('sardakk (Sardakk N\'orr)', text)

    def testNewSaveShow(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'g.json')
            created = Run('new', '--factions', 'sol,hacan,naalu', '--seed', '3',
                          '--save', path, '--no-map')
            shown = Run('show', path, '--no-map')
        self.assertIn('Saved to', created)
        self.assertEqual(created.split('\nSaved to')[0].rstrip('\n'), shown.rstrip('\n'))
        self.assertIn('hacan (The Emirates of Hacan)', shown)

    def testFactions(self):
        text = Run('factions')
        self.assertIn('sol', text)
        self.assertNotIn('saar', text)

    def testOpenSampleMapHasNoHomes(self):
        self.assertEqual(game_cli.OPEN_SAMPLE_MAP.split().count('0'), 6)


if __name__ == '__main__':
    unittest.main()
