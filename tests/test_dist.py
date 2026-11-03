"""Checks for packaging/dist/omg-dist (the distribution pipeline), in Python.

The second language for the pipeline (the first is tests/e2e-dist.sh, which shares no code or
fixtures with this file). Builds its own small git repositories, runs omg-dist against them in
temporary folders and judges what it staged. Run: python3 -m unittest tests/test_dist.py
DIST_SCRIPT=path tests another copy of omg-dist (tests/e2e-dist.sh --prove-red plants faults that way).
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
DIST = os.environ.get("DIST_SCRIPT", os.path.join(TOP, "packaging", "dist", "omg-dist"))
sys.path.insert(0, os.path.join(TOP, "packaging", "dist"))
import chan_check  # noqa: E402

ENV0 = {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def run(args, env=None, cwd=None):
    e = dict(os.environ)
    e.update(ENV0)
    e.update(env or {})
    return subprocess.run(args, env=e, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=300)


def write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def read(p):
    with open(p) as f:
        return f.read()


class Dist(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.repo = os.path.join(self.t, "origin")
        os.makedirs(self.repo)
        run(["git", "init", "-q", "-b", "main"], cwd=self.repo)
        write(os.path.join(self.repo, "debian", "changelog"), "obsmage (0.0.7) unstable; urgency=low\n\n  * x\n\n -- T <t@example.invalid>  Sun, 01 Nov 2026 12:00:00 -0600\n")
        write(os.path.join(self.repo, "atoms", "demo", "basic.ini", "set-Twitch.kv"), "Name=sample\nToken=@secret(len=21)\n")
        write(os.path.join(self.repo, "README"), "a small tree shaped like obsmage\n")
        self.commit("one", "2026-11-01T10:00:00Z")
        self.bin = os.path.join(self.t, "bin")
        os.makedirs(self.bin)

    def tearDown(self):
        shutil.rmtree(self.t)

    def commit(self, msg, when):
        run(["git", "add", "-A"], cwd=self.repo)
        r = run(["git", "commit", "-q", "-m", msg], cwd=self.repo, env={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
        self.assertEqual(r.returncode, 0, r.stderr)

    def dist(self, out, deb="no", extra=None):
        env = {"DIST_SRC": self.repo, "DIST_OUT": out, "DIST_DEB": deb, "DIST_BASE_URL": ""}
        env.update(extra or {})
        return run(["sh", DIST], env=env)

    def fake_debian_tools(self):
        """dpkg-checkbuilddeps says yes; dpkg-buildpackage packs the tree's README with the real dpkg-deb."""
        write(os.path.join(self.bin, "dpkg-checkbuilddeps"), "#!/bin/sh\nexit 0\n")
        write(os.path.join(self.bin, "dpkg-buildpackage"), """#!/bin/sh
set -e
v=$(sed -n '1s/^obsmage (\\([^)]*\\)).*/\\1/p' debian/changelog)
a=$(dpkg --print-architecture)
p=$(mktemp -d); mkdir -p "$p/DEBIAN" "$p/usr/share/doc/obsmage"
cp README "$p/usr/share/doc/obsmage/"
[ -f PLANT ] && cp PLANT "$p/usr/share/doc/obsmage/"
printf 'Package: obsmage\\nVersion: %s\\nArchitecture: %s\\nMaintainer: T <t@example.invalid>\\nDescription: test\\n' "$v" "$a" > "$p/DEBIAN/control"
find "$p" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
dpkg-deb --root-owner-group -Zgzip --build "$p" "../obsmage_${v}_${a}.deb" >/dev/null
rm -rf "$p"
""")
        for f in ("dpkg-checkbuilddeps", "dpkg-buildpackage"):
            os.chmod(os.path.join(self.bin, f), 0o755)
        return {"PATH": self.bin + os.pathsep + os.environ["PATH"]}

    # D1: a tarball named from the commit, its sha256 and size in a valid feed
    def test_stages_tarball_and_feed(self):
        out = os.path.join(self.t, "out")
        r = self.dist(out)
        self.assertEqual(r.returncode, 0, r.stderr)
        pub = os.path.join(out, "public")
        tars = [f for f in os.listdir(pub) if f.endswith(".tar.gz")]
        self.assertEqual(len(tars), 1)
        self.assertRegex(tars[0], r"^obsmage-0\.0\.7-20261101-100000-[0-9a-f]{12}\.tar\.gz$")
        feed = os.path.join(pub, "channel.json")
        self.assertIsNone(chan_check.check(feed, pub))
        text = read(feed)
        self.assertIn('"sha256": "%s"' % sha(os.path.join(pub, tars[0])), text)
        self.assertIn('"artifact": "%s"' % tars[0], text)
        self.assertIn('"key": "obsmage:', text)
        self.assertIn("deb:none", text)
        self.assertNotIn("deb_sha256", text)

    # D2: reproducible: two clean runs give the same bytes and the same feed
    def test_reproducible(self):
        a, b = os.path.join(self.t, "a"), os.path.join(self.t, "b")
        self.assertEqual(self.dist(a).returncode, 0)
        self.assertEqual(self.dist(b).returncode, 0)
        ta = sorted(f for f in os.listdir(os.path.join(a, "public")) if f.endswith(".tar.gz"))
        tb = sorted(f for f in os.listdir(os.path.join(b, "public")) if f.endswith(".tar.gz"))
        self.assertEqual(ta, tb)
        self.assertEqual(sha(os.path.join(a, "public", ta[0])), sha(os.path.join(b, "public", tb[0])))
        self.assertEqual(read(os.path.join(a, "public", "channel.json")), read(os.path.join(b, "public", "channel.json")))

    # D3: SHA256SUMS covers every bundle and record, and checks out
    def test_sha256sums(self):
        out = os.path.join(self.t, "out")
        self.dist(out)
        pub = os.path.join(out, "public")
        sums = dict(reversed(l.split("  ", 1)) for l in read(os.path.join(pub, "SHA256SUMS")).split("\n") if l)
        for f in os.listdir(pub):
            if re.match(r"^obsmage[-_].*\.(tar\.gz|deb|json)$", f):
                self.assertEqual(sums.get(f), sha(os.path.join(pub, f)), f)

    # D4: a credential in an atom, or shaped like a live key, refuses the release; nothing staged
    def test_refuses_secrets(self):
        for name, path, text in [
            ("atom", os.path.join("atoms", "demo", "basic.ini", "set-Twitch.kv"), "Name=sample\nToken=" + "r3al" * 6 + "\n"),
            ("shape", "notes.txt", "key: " + "gh" + "p_" + "A1b2C3d4" * 5 + "\n"),
            ("pem", "id.txt", "-----BEGIN " + "OPENSSH PRIVATE KEY-----\nxx\n"),
        ]:
            with self.subTest(name):
                write(os.path.join(self.repo, path), text)
                self.commit("plant " + name, "2026-11-01T11:00:00Z")
                out = os.path.join(self.t, "out-" + name)
                r = self.dist(out)
                self.assertEqual(r.returncode, 1, name)
                self.assertIn("secret-scan refused", r.stderr)
                self.assertNotIn("r3al", r.stderr + r.stdout)   # never prints the value
                self.assertEqual(os.listdir(os.path.join(out, "public")), [], name)
                run(["git", "revert", "--no-edit", "HEAD"], cwd=self.repo, env={"GIT_COMMITTER_DATE": "2026-11-01T11:30:00Z"})

    # D5: FAKE-marked test credentials pass, as the tree's own fixtures do
    def test_fake_marked_passes(self):
        write(os.path.join(self.repo, "fixtures", "service.json"), '{"key": "live_123456789_FAKEFAKEFAKEFAKEFAKE00"}\n')
        self.commit("fixture", "2026-11-01T12:00:00Z")
        self.assertEqual(self.dist(os.path.join(self.t, "out")).returncode, 0)

    # D6: the same commit again is nothing new; a new commit is a new release and the old stays
    def test_nothing_new_then_new(self):
        out = os.path.join(self.t, "out")
        self.dist(out)
        pub = os.path.join(out, "public")
        before = sorted(os.listdir(pub))
        r = self.dist(out, extra={"DIST_SRC": self.repo})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(sorted(os.listdir(pub)), before)
        write(os.path.join(self.repo, "README"), "changed\n")
        self.commit("two", "2026-11-02T10:00:00Z")
        self.assertEqual(self.dist(out).returncode, 0)
        tars = sorted(f for f in os.listdir(pub) if f.endswith(".tar.gz"))
        self.assertEqual(len(tars), 2)
        self.assertIn("20261102-100000", read(os.path.join(pub, "channel.json")))

    # D7: retention keeps DIST_KEEP (never fewer than 3), the newest named by the feed
    def test_retention(self):
        out = os.path.join(self.t, "out")
        for i in range(5):
            write(os.path.join(self.repo, "README"), "v%d\n" % i)
            self.commit("v%d" % i, "2026-11-0%dT10:00:00Z" % (i + 2))
            self.assertEqual(self.dist(out, extra={"DIST_KEEP": "1"}).returncode, 0)
        pub = os.path.join(out, "public")
        tars = sorted(f for f in os.listdir(pub) if f.endswith(".tar.gz"))
        self.assertEqual(len(tars), 3)
        self.assertIn(tars[-1], read(os.path.join(pub, "channel.json")))
        self.assertEqual(len([f for f in os.listdir(pub) if f.endswith(".json") and f != "channel.json"]), 3)

    # D8: the Debian package: built when the tools are there, named from the commit, in the feed, scanned too
    def test_deb(self):
        env = self.fake_debian_tools()
        out = os.path.join(self.t, "out")
        r = self.dist(out, deb="auto", extra=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        pub = os.path.join(out, "public")
        debs = [f for f in os.listdir(pub) if f.endswith(".deb")]
        self.assertEqual(len(debs), 1)
        self.assertRegex(debs[0], r"^obsmage_0\.0\.7\+git20261101\.100000\.[0-9a-f]{7}_[a-z0-9]+\.deb$")
        self.assertIsNone(chan_check.check(os.path.join(pub, "channel.json"), pub))
        self.assertIn('"deb_sha256": "%s"' % sha(os.path.join(pub, debs[0])), read(os.path.join(pub, "channel.json")))
        # the same commit, built again elsewhere: the same package bytes
        out2 = os.path.join(self.t, "out2")
        self.assertEqual(self.dist(out2, deb="auto", extra=env).returncode, 0)
        self.assertEqual(sha(os.path.join(pub, debs[0])), sha(os.path.join(out2, "public", debs[0])))
        # a secret that reaches only the package is refused too
        write(os.path.join(self.repo, "PLANT"), "token " + "xo" + "xb-" + "1234567890-abcdefghij" + "\n")
        self.commit("plant", "2026-11-03T10:00:00Z")
        r = self.dist(os.path.join(self.t, "out3"), deb="auto", extra=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("refused", r.stderr)

    # D9: a run in progress is not overlapped
    def test_lock(self):
        out = os.path.join(self.t, "out")
        os.makedirs(os.path.join(out, "work", "lock"))
        sleeper = subprocess.Popen(["sleep", "30"])
        try:
            write(os.path.join(out, "work", "lock", "pid"), "%d\n" % sleeper.pid)
            r = self.dist(out)
            self.assertEqual(r.returncode, 0)
            self.assertFalse(os.path.exists(os.path.join(out, "public", "channel.json")))
        finally:
            sleeper.kill()
            sleeper.wait()   # reaped, or its zombie still answers kill -0
        self.assertEqual(self.dist(out).returncode, 0)   # a dead pid's lock is taken over
        self.assertTrue(os.path.exists(os.path.join(out, "public", "channel.json")))

    # D10: the feed checker refuses what the spec refuses
    def test_chan_check(self):
        p = os.path.join(self.t, "f.json")
        good = ['{', '  "format": "channel/1",', '  "channel": "obsmage",', '  "revision": "0123456789abcdef",', '  "stamp": "20261101-100000",',
                '  "artifact": "obsmage-0.0.7-20261101-100000-0123456789ab.tar.gz",', '  "sha256": "' + "a" * 64 + '",', '  "key": "obsmage:0123456789ab:0.0.7"', '}']
        write(p, "\n".join(good) + "\n")
        self.assertIsNone(chan_check.check(p))
        for bad in [lambda g: ['{' + "".join(x.strip() for x in g[1:])], lambda g: g[:2] + g[3:],
                    lambda g: g[:7] + ['  "key": "obsmage:x",'] + g[8:], lambda g: g[:8] + ['  "deb": "obsmage_1_amd64.deb"', '}'],
                    lambda g: [g[0], g[1].replace("channel/1", "channel/2")] + g[2:]]:
            write(p, "\n".join(bad(good)) + "\n")
            self.assertIsNotNone(chan_check.check(p))


if __name__ == "__main__":
    unittest.main()

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
