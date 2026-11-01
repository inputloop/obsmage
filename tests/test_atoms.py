"""Unit tests for tools/omg_atoms.py. Run: python3 -m unittest discover -s tests -p 'test_atoms.py'
OMG_PROVE_RED=1 plants a fault (the leak check is fed a published copy of a secret) and the
suite must then fail: a green suite that cannot fail is not a test."""
import os, shutil, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import omg_atoms as A  # noqa: E402

FIX = os.path.join(HERE, 'fixtures', 'config-small')
RED = os.environ.get('OMG_PROVE_RED') == '1'


class Atoms(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.atoms, self.vault = os.path.join(self.t, 'atoms'), os.path.join(self.t, 'v.kv')

    def tearDown(self):
        shutil.rmtree(self.t)

    def test_round_trip_lossless(self):
        bad, missing, leaks = A.verify(FIX)
        self.assertEqual((bad, missing, leaks), ([], [], []))

    def test_ini_byte_exact_bom_crlf(self):
        data = open(os.path.join(FIX, 'basic/profiles/Demo/basic.ini'), 'rb').read()
        meta, shape, sets = A.split_ini(data)
        self.assertTrue(meta['bom'] and meta['crlf'])
        self.assertEqual(A.join_ini(meta, shape, sets), data)

    def test_secrets_never_published(self):
        n = A.split(FIX, self.atoms, self.vault)
        self.assertEqual(n['secret'], 4)  # Token, RefreshToken, AuthSecret, stream key
        published = ''.join(open(os.path.join(d, f), encoding='utf-8').read()
                            for d, _, fs in os.walk(self.atoms) for f in fs)
        if RED:
            published += 'FAKEFAKEFAKEtoken0000'
        for secret in ('FAKEFAKEFAKEtoken0000', 'FAKEsecretFAKEsecret==', 'live_FAKE_stream_key_123456'):
            self.assertNotIn(secret, published)
        if os.name != 'nt':  # Windows has no mode bits; see test_windows_py38 for the ACL path
            self.assertEqual(os.stat(self.vault).st_mode & 0o777, 0o600)

    def test_join_refuses_without_vault(self):
        A.split(FIX, self.atoms, self.vault)
        missing = A.join(self.atoms, os.path.join(self.t, 'out'), None)
        self.assertEqual(len(missing), 4)

    def test_classes(self):
        self.assertEqual(A.classify('Token', 'abcdef'), 'secret')
        self.assertEqual(A.classify('Token', ''), 'plain')
        self.assertEqual(A.classify('/settings/monitor_id', '"x"'), 'device')
        self.assertEqual(A.classify('FilePath', 'C:\\Users\\x'), 'path')
        self.assertEqual(A.classify('BaseCX', '1920'), 'plain')

    def test_json_pointer_edge_keys(self):
        obj = {'a/b': 1, '#x': [1, {}, []], '~t': {'': None}, 'n': 'line\nbreak = :x'}
        self.assertEqual(A.unflatten(list(A.flatten(obj))), obj)

    def test_rollup_unroll_and_conflict(self):
        A.split(FIX, self.atoms, self.vault)
        st = os.path.join(self.t, 'STAGES.md')
        A.rollup(self.atoms, st)
        text = open(st, encoding='utf-8').read()
        self.assertNotIn('FAKEFAKEFAKEtoken0000', text)
        open(st, 'w', encoding='utf-8').write(text.replace('BaseCX=1920', 'BaseCX=2560'))
        self.assertEqual(A.unroll(st, self.atoms), [])
        self.assertIn('BaseCX=2560', open(os.path.join(
            self.atoms, 'basic/profiles/Demo/basic.ini/set-Video.kv'), encoding='utf-8').read())
        # second writer: atoms change AND the roll-up changes -> stop, write nothing
        A.rollup(self.atoms, st)
        kv = os.path.join(self.atoms, 'basic/profiles/Demo/basic.ini/set-Video.kv')
        open(kv, 'a', encoding='utf-8').write('Extra=1\n')
        t2 = open(st, encoding='utf-8').read().replace('BaseCY=1080', 'BaseCY=1440')
        open(st, 'w', encoding='utf-8').write(t2)
        errs = A.unroll(st, self.atoms)
        self.assertTrue(errs and 'both sides changed' in errs[0])
        self.assertIn('BaseCY=1080', open(kv, encoding='utf-8').read())

    def test_ledger_suggest_never_moves(self):
        led = os.path.join(self.t, 'ledger')
        cfg = os.path.join(self.t, 'cfg'); shutil.copytree(FIX, cfg)
        A.split(cfg, self.atoms, self.vault, led)
        ini = os.path.join(cfg, 'basic/profiles/Demo/basic.ini')
        orig = open(ini, 'rb').read()
        for i in range(3):  # Video and WebsocketAPI change together three times
            d = orig.replace(b'BaseCX=1920', b'BaseCX=19%d' % (30 + i))
            d = d.replace(b'ServerPort=4444', b'ServerPort=45%d' % (10 + i))
            open(ini, 'wb').write(d)
            A.split(cfg, self.atoms, self.vault, led)
        before = sorted(os.listdir(os.path.join(self.atoms, 'basic/profiles/Demo/basic.ini')))
        rows = A.suggest(led, 3)
        self.assertTrue(any('Video' in a + b and 'WebsocketAPI' in a + b for _, a, b in rows))
        self.assertEqual(before, sorted(os.listdir(os.path.join(self.atoms, 'basic/profiles/Demo/basic.ini'))))


if __name__ == '__main__':
    unittest.main()

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin; claude-opus-5-5)
