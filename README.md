# obsmage

**OBS Studio, kept as a living, literate configuration, with plugins that sense the room.**

obsmage is a downstream build of [OBS Studio](https://obsproject.com). It wraps the whole OBS
configuration in a key/value *atom* layer, so every setting can be read, diffed, versioned,
reviewed and changed by a person or a tool, with credentials kept out of everything published.
On top of that sit plugins, each of which also installs into an upstream OBS you built yourself.

## What works today

| | |
|---|---|
| `tools/omg_atoms.py` | Splits a whole OBS configuration into atoms and joins it back losslessly (INI byte-exact, JSON parse-equal). Credentials go to a local vault (mode 600) and are never published. Also: the `STAGES.md` roll-up, unroll with two-sided conflict detection, and the co-change ledger. Tested on a real 1.6 MB, 27,800-atom setup. |
| `tools/omg_compose.py` | Multi-monitor composer: audits which captures bind to a display by index (fragile) or by stable id, rebinds them, and keeps your screen-map scenes current. Never deletes; hides and reports. |
| `packaging/healer/omg-heal` | The build healer: plan, build and heal Debian and source builds, following `main` (the default), project meta, tags, or signed tags only. |
| `packaging/healer/omg-load-check` | The test instance: after every good heal, the newest package's plugin is loaded in this host's OBS Studio under a virtual display, in a throwaway HOME, and the result recorded. |
| `packaging/dist/omg-dist` | The distribution pipeline: from one commit, a reproducible source tarball and the Debian package, each with its sha256, named in a channel feed; every bundle is scanned for credentials before it is staged. Served at https://obsmage.com/dist/. |
| `packaging/windows/omg-win` | Windows x64, the shortest path: the core plugin cross-built with MinGW-w64 against OBS Studio's own headers, an installer that puts it and the two tools into the OBS Studio you already have (it looks in the registry and Program Files, and lets you browse when that fails), and a zip of the same files; each with its sha256. Built and checked in CI (`.github/workflows/windows.yml`); not published yet. **Not signed:** Windows SmartScreen warns about the installer; choose "More info", then "Run anyway". |
| `site/` | https://obsmage.com, built by our own toolchain, with a browser demo that splits an invented OBS setup into atoms and joins it back, byte for byte. `site/README.md`. |

## What is designed, not built

AR desktop control (magic hand, flick to fill, magic wand, wall grab) and camera calibration:
[`docs/AR-CONTROL.md`](docs/AR-CONTROL.md). The core plugin skeleton is in `plugin/obsmage-core`; it compiles against Ubuntu's libobs and loads in OBS Studio 32.1.0 on gw33 (log lines in `docs/REQUIREMENTS.md`); its menu entries only log for now.
Full status table: [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md).

## Try it

```sh
python3 tools/omg_atoms.py find                                  # where is my OBS config?
python3 tools/omg_atoms.py verify ~/.config/obs-studio           # lossless? secrets kept back?
python3 tools/omg_atoms.py split ~/.config/obs-studio atoms/ --ledger ledger/
python3 tools/omg_atoms.py rollup atoms/ STAGES.md               # one file to read and edit
python3 tools/omg_compose.py audit ~/.config/obs-studio/basic/scenes/MyScenes.json
```

`verify` and `audit` only read. Nothing writes your live OBS files without `--write`, and every
write leaves a dated backup.

## Tests

```sh
python3 -m unittest discover -s tests          # Python unit tests
sh tests/e2e.sh                                 # POSIX sh end-to-end, against tests/SPEC.txt
sh tests/e2e.sh --prove-red                     # shows the suite can fail
sh tests/e2e-healer.sh
sh tests/e2e-packaging.sh                       # debian/ and the user-mode healer units
sh tests/e2e-dist.sh                            # the distribution pipeline (tests/test_dist.py is its second language)
sh tests/e2e-loadcheck.sh                       # the test instance, against a fake OBS
sh tests/e2e-windows.sh                         # the Windows build, on Linux (tests/windows_pe_check.pl is its second language)
sh site/tests/run.sh                            # the site: static, JS-against-Python vectors, install, browser
python3 -m unittest tests/test_windows_py38.py  # Windows / Python 3.8 cases
```

Each shell suite takes `--prove-red` (the healer's: `HEAL_PROVE_RED=1`); the Python tests take
`OMG_PROVE_RED=1`; `site/tests/run.sh --prove-red` plants a fault for each of the site's promises. All of it runs on Python 3.8 (Avalon's Windows Python).

## How this tree is kept

[`CONVENTIONS.md`](CONVENTIONS.md): atoms, classes, the `STAGES.md` seam (two readers, two
writers), and why nothing gets reorganized automatically. A tool may point out a pattern; a person
decides. The journal (`journal/YYYY/MM/DD/`) says why things changed.

Personal recipes (one person's rig, cameras and scenes) live in their own repositories that consume
this one. `inputloop/obsmage-corwin` is the first.

---
Corwin and Bryant (BryantAndCorwin@inputloop.com) · inputloop

Copyright 2026 INPUTLOOP; code GPL-3.0-or-later OR LGPL-3.0-or-later; prose CC-BY-SA-4.0.
Mentat (for Corwin; claude-opus-5-5)
