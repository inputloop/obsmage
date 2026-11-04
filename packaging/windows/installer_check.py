#!/usr/bin/env python3
"""installer_check.py: on Windows, hold the obsmage installer and uninstaller to what they promise.

    python installer_check.py snapshot OBS_DIR FILE        list every file and folder under OBS_DIR into FILE
    python installer_check.py refuses SETUP                silently into an empty folder that is not OBS Studio:
                                                           it must exit non-zero and write nothing there
    python installer_check.py installs SETUP ZIP OBS_DIR   silently, with no folder given: it must find OBS_DIR by
                                                           itself, put every file of ZIP there byte for byte, and
                                                           add a Settings > Apps entry naming OBS_DIR
    python installer_check.py uninstalls OBS_DIR FILE      the uninstaller, silently: OBS_DIR must be exactly as
                                                           FILE lists it, and the Apps entry gone
    python installer_check.py --prove-red PLANTED ZIP OBS_DIR FILE
                                                           the same checks on a planted installer (refusal removed,
                                                           uninstaller forgets the DLL): refuses and uninstalls
                                                           must fail; installs must still pass
Exit 0 held, 1 not held, 2 usage. Windows, Python 3.8 or later, standard library only. Run as an administrator
(the installer writes into Program Files and HKLM). The installer is packaging/windows/obsmage.nsi.
"""
import hashlib
import os
import subprocess
import sys
import tempfile
import time
import zipfile

UNINST = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\obsmage"
UNINSTALLER = os.path.join("data", "obs-plugins", "obsmage-core", "uninstall-obsmage.exe")


def apps_entry():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, UNINST, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            out = {}
            for n in ("DisplayName", "DisplayVersion", "InstallLocation", "MadeObsPlugins", "MadeObsPlugins64", "MadeDataObsPlugins"):
                try:
                    out[n] = winreg.QueryValueEx(k, n)[0]
                except OSError:
                    out[n] = None
            return out
    except OSError:
        return None


def tree(root):
    out = []
    for dp, dirs, files in os.walk(root):
        rel = os.path.relpath(dp, root)
        for n in dirs:
            out.append(os.path.normpath(os.path.join(rel, n)) + "\\")
        for n in files:
            out.append(os.path.normpath(os.path.join(rel, n)))
    return sorted(out)


def same_dir(a, b):
    return os.path.normcase(os.path.normpath(a or "")) == os.path.normcase(os.path.normpath(b or ""))


def run(cmdline):
    # one string: NSIS takes /D= unquoted, as the last argument, spaces and all
    return subprocess.run(cmdline).returncode


def report(found, what):
    for text, ok in found:
        print("  %s  %s" % ("ok " if ok else "RED", text))
    good = all(ok for _, ok in found)
    print("installer_check %s: %s" % (what, "held" if good else "NOT HELD"), flush=True)
    return 0 if good else 1


def snapshot(obs_dir, path):
    t = tree(obs_dir)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(t) + "\n")
    print("installer_check snapshot: %d files and folders under %s" % (len(t), obs_dir))
    return 0


def refuses(setup):
    d = tempfile.mkdtemp(prefix="not-obs-")
    had = apps_entry()
    rc = run('"%s" /S /D=%s' % (setup, d))
    left = os.listdir(d)
    found = [("exits non-zero for %s (exit %d)" % (d, rc), rc != 0),
             ("writes nothing there (%s)" % (", ".join(left[:5]) or "empty"), not left)]
    if had is None:
        found.append(("adds no Apps entry", apps_entry() is None))
    return report(found, "refuses")


def installs(setup, zip_path, obs_dir):
    rc = run('"%s" /S' % setup)
    found = [("exits 0 with no folder given (exit %d)" % rc, rc == 0)]
    with zipfile.ZipFile(zip_path) as z:
        for name in sorted(n for n in z.namelist() if not n.endswith("/")):
            p = os.path.join(obs_dir, *name.split("/"))
            got = None
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    got = hashlib.sha256(f.read()).hexdigest()
            found.append(("%s, byte for byte" % name, got == hashlib.sha256(z.read(name)).hexdigest()))
    found.append(("the uninstaller is there", os.path.isfile(os.path.join(obs_dir, UNINSTALLER))))
    e = apps_entry()
    found.append(("an Apps entry naming %s (%s)" % (obs_dir, e and e.get("InstallLocation")), bool(e) and same_dir(e.get("InstallLocation"), obs_dir)))
    if e:
        print("  Apps entry: %r" % e)
    return report(found, "installs")


def uninstalls(obs_dir, path):
    with open(path, encoding="utf-8") as f:
        before = [l for l in f.read().split("\n") if l]
    u = os.path.join(obs_dir, UNINSTALLER)
    found = [("the uninstaller is there", os.path.isfile(u))]
    if os.path.isfile(u):
        run('"%s" /S' % u)  # it copies itself to %TEMP% and returns; the copy does the work
        deadline = time.time() + 90
        while time.time() < deadline and (apps_entry() is not None or os.path.exists(u)):
            time.sleep(1)
    now = tree(obs_dir)
    added = sorted(set(now) - set(before))
    gone = sorted(set(before) - set(now))
    found.append(("nothing left behind (%s)" % (", ".join(added[:8]) or "none"), not added))
    found.append(("nothing of OBS Studio's removed (%s)" % (", ".join(gone[:8]) or "none"), not gone))
    found.append(("the Apps entry is gone", apps_entry() is None))
    return report(found, "uninstalls")


def prove_red(planted, zip_path, obs_dir, path):
    me = [sys.executable, os.path.abspath(__file__)]
    runs = [("the planted installer installs into a folder that is not OBS Studio", ["refuses", planted], 1),
            ("it still installs into OBS Studio (so the next failure is the plant's)", ["installs", planted, zip_path, obs_dir], 0),
            ("its uninstaller leaves the DLL behind", ["uninstalls", obs_dir, path], 1)]
    bad = 0
    for what, args, want in runs:
        r = subprocess.run(me + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=600)
        reds = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("RED")]
        right = r.returncode == want
        bad += 0 if right else 1
        print("%s  %s (exit %d, wanted %d%s)" % ("ok " if right else "RED", what, r.returncode, want, "; " + reds[0] if reds else ""))
    print("PROVE-RED OK" if bad == 0 else "PROVE-RED FAILED")
    return 0 if bad == 0 else 1


def main(argv):
    cmds = {"snapshot": (2, snapshot), "refuses": (1, refuses), "installs": (3, installs),
            "uninstalls": (2, uninstalls), "--prove-red": (4, prove_red)}
    if not argv or argv[0] not in cmds or len(argv) - 1 != cmds[argv[0]][0]:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    return cmds[argv[0]][1](*argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
