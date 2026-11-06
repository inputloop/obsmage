"""Checks for the things that bite on Avalon: Windows Python 3.8 (32-bit), cp1252 consoles, CRLF.
Run: python3 -m unittest discover -s tests -p 'test_windows_py38.py' -v
Set OMG_PROVE_RED=1 to plant faults and watch the suite go red.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
TOOLS = os.path.join(TOP, "tools")
FIX = os.path.join(HERE, "fixtures")
RED = os.environ.get("OMG_PROVE_RED") == "1"

# Python 3.9+ library calls that the syntax check cannot see.
NEWER_CALLS = (".removeprefix(", ".removesuffix(", "functools.cache(", "math.lcm(", "zoneinfo")


class Syntax38(unittest.TestCase):
    def test_tools_parse_as_python_38(self):
        for name in ("omg_atoms.py", "omg_compose.py"):
            with open(os.path.join(TOOLS, name), encoding="utf-8") as f:
                src = f.read()
            if RED:
                src += "\nif (y := 1):\n    pass\nmatch = 1\nwith (open('a') as a, open('b') as b):\n    pass\n"
            ast.parse(src, feature_version=(3, 8))
            for bad in NEWER_CALLS:
                self.assertNotIn(bad, src, "%s uses %s, which Python 3.8 lacks" % (name, bad))


class Cp1252Console(unittest.TestCase):
    """A Windows console or redirect is cp1252 by default. A source named with a character
    outside it must not crash a print."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        with open(os.path.join(FIX, "three-heads.json"), encoding="utf-8") as f:
            col = json.load(f)
        col["sources"][0]["name"] = "Écran — 日本"  # outside cp1252 in part
        self.col = os.path.join(self.tmp, "c.json")
        with open(self.col, "w", encoding="utf-8") as f:
            json.dump(col, f, ensure_ascii=False)

    def run_compose(self, *args):
        guard = "import omg_compose as m, sys\n"
        if RED:
            guard += "m._utf8_streams = lambda: None\n"  # planted fault: the guard is gone
        guard += "sys.exit(m.main(sys.argv[1:]))\n"
        env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONPATH=TOOLS)
        return subprocess.run([sys.executable, "-c", guard] + list(args), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_audit_survives_cp1252(self):
        r = self.run_compose("audit", self.col)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        self.assertIn("Écran".encode("utf-8"), r.stdout)

    def test_compose_out_is_lf_utf8(self):
        out = os.path.join(self.tmp, "o.json")
        disp = os.path.join(FIX, "displays-four.json")
        r = self.run_compose("compose", self.col, "--displays", disp, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        raw = open(out, "rb").read()
        self.assertNotIn(b"\r", raw)
        self.assertIn("日本".encode("utf-8"), raw)

    def test_displays_out_writes_file(self):
        out = os.path.join(self.tmp, "d.json")
        disp = os.path.join(FIX, "displays-four.json")
        r = self.run_compose("displays", "--from", disp, "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        raw = open(out, "rb").read()
        self.assertFalse(raw.startswith(b"\xff\xfe"), "UTF-16 BOM")
        self.assertEqual(len(json.loads(raw.decode("utf-8"))), 4)


class MixedLineEndings(unittest.TestCase):
    """Seen on Avalon: OBS appended CRLF lines to LF profile files. The split must be lossless."""

    def make(self, raw):
        tmp = tempfile.mkdtemp()
        d = os.path.join(tmp, "cfg", "basic", "profiles", "P")
        os.makedirs(d)
        with open(os.path.join(d, "basic.ini"), "wb") as f:
            f.write(raw)
        return tmp, os.path.join(tmp, "cfg")

    def roundtrip(self, raw):
        tmp, cfg = self.make(raw)
        sys.path.insert(0, TOOLS)
        import omg_atoms as oa
        atoms, out = os.path.join(tmp, "atoms"), os.path.join(tmp, "out")
        oa.split(cfg, atoms, os.path.join(tmp, "v.kv"))
        oa.join(atoms, out, oa.load_vault(os.path.join(tmp, "v.kv")))
        return open(os.path.join(out, "basic", "profiles", "P", "basic.ini"), "rb").read()

    def test_mixed_lf_and_crlf(self):
        raw = b"[General]\nName=P\n[AdvOut]\r\nEncoder=nvenc\r\n"
        if RED:  # planted fault: the round trip is compared with a changed copy
            raw2 = raw.replace(b"[AdvOut]\r\n", b"[AdvOut]\n")
        self.assertEqual(self.roundtrip(raw), raw if not RED else raw2)

    def test_mixed_no_trailing_newline(self):
        raw = b"[A]\nx=1\r\ny=2"
        self.assertEqual(self.roundtrip(raw), raw)

    def test_json_lines_file_survives(self):
        """Chromium's FirstPartySets/sets.json inside obs-browser's folder is one JSON per line."""
        tmp = tempfile.mkdtemp()
        d = os.path.join(tmp, "cfg", "plugin_config", "x")
        os.makedirs(d)
        raw = b'{"a":1}\r\n{"b":"\xff"}\r\n'  # includes a byte that is not UTF-8
        with open(os.path.join(d, "sets.json"), "wb") as f:
            f.write(raw)
        sys.path.insert(0, TOOLS)
        import omg_atoms as oa
        atoms, out = os.path.join(tmp, "atoms"), os.path.join(tmp, "out")
        oa.split(os.path.join(tmp, "cfg"), atoms, os.path.join(tmp, "v.kv"))
        oa.join(atoms, out, oa.load_vault(os.path.join(tmp, "v.kv")))
        got = open(os.path.join(out, "plugin_config", "x", "sets.json"), "rb").read()
        self.assertEqual(got, raw if not RED else b"")

    def test_lone_cr_inside_a_value(self):
        raw = b"[A]\nx=a\rb\ny=2\n"
        self.assertEqual(self.roundtrip(raw), raw)


class WindowsVaultLock(unittest.TestCase):
    """On Windows the vault is locked to its owner with icacls (no mode bits there)."""

    def test_vault_gets_an_owner_only_acl(self):
        from unittest import mock
        sys.path.insert(0, TOOLS)
        import omg_atoms as oa
        calls = []

        def fake_run(argv, **kw):
            calls.append(argv)
            return mock.Mock(returncode=0)
        tmp = tempfile.mkdtemp()
        env = dict(os.environ, USERNAME="corwi")
        with mock.patch.object(oa, "IS_WINDOWS", not RED), mock.patch("subprocess.run", fake_run), \
                mock.patch.dict(os.environ, env):
            oa.save_vault(os.path.join(tmp, "v.kv"), {"a|b|c": "x"})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "icacls")
        self.assertIn("/inheritance:r", calls[0])
        self.assertIn("corwi:F", calls[0])

    def test_failure_warns_and_does_not_crash(self):
        from unittest import mock
        sys.path.insert(0, TOOLS)
        import omg_atoms as oa
        tmp = tempfile.mkdtemp()
        with mock.patch.object(oa, "IS_WINDOWS", True), \
                mock.patch("subprocess.run", side_effect=OSError("no icacls")):
            import io
            err = io.StringIO()
            with mock.patch("sys.stderr", err):
                oa.save_vault(os.path.join(tmp, "v.kv"), {"a|b|c": "x"})
        self.assertIn("could not restrict", err.getvalue())
        self.assertTrue(os.path.exists(os.path.join(tmp, "v.kv")))


class ZipLayout(unittest.TestCase):
    """The Windows zip is OBS Studio 33's per-plugin layout (frontend/plugin-manager/PluginModuleLoader_Windows.cpp:
    <Root Path>/obs-studio/plugins/<Plugin>/<Plugin>.dll and .../<Plugin>/data). installer_check.in_obs_dir is how
    the Windows CI finds each zip file where the installer wrote it; it must take only that layout. The sh witness
    is tests/e2e-windows.sh W13, which reads a real built zip."""

    def test_in_obs_dir(self):
        sys.path.insert(0, os.path.join(TOP, "packaging", "windows"))
        try:
            import installer_check as ic
        finally:
            sys.path.pop(0)
        cases = {
            "obsmage-core/obsmage-core.dll": "obs-plugins/64bit/obsmage-core.dll",
            "obsmage-core/data/locale/en-US.ini": "data/obs-plugins/obsmage-core/locale/en-US.ini",
            "obsmage-core/data/tools/omg_atoms.py": "data/obs-plugins/obsmage-core/tools/omg_atoms.py",
            "obsmage-core/bin/64bit/obsmage-core.dll": None,      # OBS 33 calls this legacy
            "obs-plugins/64bit/obsmage-core.dll": None,           # the OBS-folder layout, also legacy
            "obsmage-core/README-windows.txt": None,              # beside the DLL, not in data/
            "obsmage-core/data/../../evil.dll": None,
        }
        if RED:  # planted fault: the legacy bin/64bit path is expected to be taken
            cases["obsmage-core/bin/64bit/obsmage-core.dll"] = "obs-plugins/64bit/obsmage-core.dll"
        for name, want in cases.items():
            self.assertEqual(ic.in_obs_dir(name), want, name)


if __name__ == "__main__":
    unittest.main()
