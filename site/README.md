# obsmage.com: the site

The website at https://obsmage.com, built from this folder the way corwin.cloud is built: plain
files, no framework, nothing from another host. `build.py` writes `public/` (what nginx serves) and
`generated/` (two nginx snippets). Python 3.8 or later, standard library only.

## What is on it

- **The front page**: what obsmage is, in plain words; the picture (OBS → atoms → composer →
  healer → releases), drawn in topology forge, the drawing app that opens corwin.cloud, staged from
  a topology checkout (branch `corwin`) by its own `bin/stage-www.sh`; on a phone, or without
  scripts, the same picture as a figure; what each part does; releases; why; how the page was made.
- **The demo** (`demo.html`), single user, all in the browser: an invented OBS setup
  (`sample/make-sample.py` writes it: no real profile, screens, devices, hosts or credentials)
  split into atoms by `src/js/omg-atoms.js`, a fresh JavaScript port of `tools/omg_atoms.py`.
  Edit an atom and the OBS file is joined again; every join is split once more and compared with
  the atoms, byte for byte, and the page says so. The screen map comes from `src/js/omg-compose.js`
  (the audit half of `tools/omg_compose.py`): drag a screen or use the arrow keys and its position
  atoms change; "Propose stable ids" shows the atoms the composer would add, and adds them only on
  request. A visitor's own files can be split too; they are read in the page and never sent (the
  page's policy allows no connection at all).
- **Releases** at `/dist/`: the bundles `packaging/dist/omg-dist` stages on gw33, with
  `SHA256SUMS` and the channel feed `/dist/channel.json`.
- **Colophon** with every part's maker and licence; **JavaScript licences** for GNU LibreJS.

## The one line: releases

`site.conf` holds `releases: open` or `releases: closed`. Open, `generated/releases.conf` maps
`/dist/` to `/var/lib/obsmage-dist/public/` and the page links the feed; closed, nothing is mapped
(a 404) and the page says releases open when the project does. The pipeline stages either way.

- 2026-11-02 17:44 CT: Corwin made inputloop/obsmage and inputloop/obsmage-corwin public ("both
  obsmage and obsmage-corwin are now public"). That met the unlock he had been asked for ("obsmage
  is public; publish its releases"), so the line was set to `open` the same evening.
- To take `/dist/` down: set `releases: closed`, rebuild, install. Nothing staged is deleted.

## Build, check, install

    TOPOLOGY_DIR=../topology python3 site/build.py      # writes site/public and site/generated
    sh site/tests/run.sh                                # ends ALL CHECKS PASSED
    sh site/tests/run.sh --prove-red                    # one planted fault per promise; ends PROVE-RED OK

On gw33, as the gw33 account (it has sudo), from an unpacked build (`public/`, `deploy/`,
`generated/` side by side): `sh deploy/install.sh` (backs up first to
`/var/backups/obsmage.com/<stamp>/`, puts the previous files back if `nginx -t` fails, and waits
for the reload to answer with its own id), `sh deploy/install-tls.sh` once (certbot webroot, both
names; certbot's timer renews), `sh deploy/rollback.sh [STAMP]` to go back.

## The checks

`tests/check_site.py` (links, the allow-list of public addresses, no inline script or style,
LibreJS labels, no network calls in our scripts, the sample invented and served byte for byte, the
deploy policies strict, releases following site.conf, the drawing whole, labels and landmarks);
`tests/atoms-vectors.mjs` and `tests/compose-vectors.mjs` (the JavaScript against the Python
tools' own output, on the repository's fixtures, the sample and written edge cases: key order,
Python's float spelling, Unicode case folding, mixed line endings, a BOM); `tests/test-install.sh`
(install, backup, undo, rollback, the reload wait, against a fake nginx); `tests/browser.cjs`
(Chromium at 390, 1280 and 1920, light and dark: no console error, no request to another host, no
sideways scroll, text contrast at WCAG 2.1 AA, and the demo worked end to end).

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin, claude-opus-5-5)
