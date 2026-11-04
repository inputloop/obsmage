# obsmage requirements

Corwin's requirements (2026-11-01), each with where it stands. **Built** means code and tests are
in this tree. **Designed** means a document says how. **Open** means neither yet.

| # | Requirement | State | Where |
|---|---|---|---|
| R1 | A bespoke multiplatform OBS (Linux, Windows, macOS) | Designed. **Windows, the shortest path, built** (2026-11-04): an unsigned installer puts the core plugin and the tools into an OBS Studio already installed; in CI it finds OBS, libobs 32.1.0 and 33.0.1 load the plugin, and OBS Studio itself logs it loaded (evidence below). Not published. The bespoke Windows build of OBS itself is designed only | `docs/PACKAGING.md`, `packaging/windows/` |
| R2 | Distribution packaging first. Carry our patches in-tree against upstream versions; prefer what upstream already does well; offer patches upstream when ready, while still using our own copy | Designed | `docs/PACKAGING.md`, `packaging/` |
| R3 | A literate taxonomy over OBS configuration: a total wrap on the OBS API and config | Built (config); Open (API) | `tools/omg_atoms.py`, `STAGES.md`, `CONVENTIONS.md` |
| R4 | Our own features as OBS plugins | Skeleton; **compiles, links and loads** in OBS Studio 32.1.0 (Ubuntu 26.04, gw33, 2026-11-01; evidence below), and since 2026-11-02 that is **re-checked after every heal** by `omg-load-check` (the test instance). Its menu entries are not yet clicked and do nothing but log | `plugin/obsmage-core/`, `packaging/healer/omg-load-check` |
| R5 | A decomposed-tree distribution setup, plus a system-service healer for regular Debian and source builds. Optional pull before build. Follow modes: tagged+signed, tagged, project meta, or main (**main is the default**) | Built. The healer built an obsmage add-on `.deb` of this repo on gw33 following `main` (2026-11-01) and runs there as a systemd user timer. A deb of OBS itself (upstream + patch queue) is **not** built: there is no patch queue and no `debian/` overlay for OBS yet | `packaging/healer/omg-heal`, `tests/e2e-healer.sh`, `debian/`, `packaging/healer/user/` |
| R6 | A physical-space-to-graphical-space map (a local service: ours, or bring your own) | Designed | `docs/AR-CONTROL.md` |
| R7 | AR desktop control mode. Releases on context menu, Start menu, ESC, Space or any click. Needs 2+ cameras and calibration reachable from the OBS UI with only the core plugin loaded | Designed | `docs/AR-CONTROL.md` |
| R7.1 | Magic hand | Designed | ″ |
| R7.2 | Flick to fill | Designed | ″ |
| R7.3 | Magic wand | Designed | ″ |
| R7.4 | Wall grab | Designed | ″ |
| R7.5 | Multi-head scene detector and auto-composer | **Built** (tool); plugin wiring Open | `tools/omg_compose.py`, `docs/COMPOSER.md` |
| R8 | No telemetry or feedback-loop work in this phase | Held | (decision, 2026-11-01) |
| R9 | The distribution pipeline (2026-11-02): versioned bundles, each with its sha256, and a channel feed | **Built**: a reproducible source tarball and the Debian package from each commit, scanned for credentials, staged on gw33 and served at https://obsmage.com/dist/ (evidence below) | `packaging/dist/`, `tests/e2e-dist.sh`, `tests/test_dist.py` |
| R10 | obsmage.com, "a mint of our cloud with itself" (2026-11-02): built by our own toolchain, with a single-user demo in the browser | **Built** and live: topology forge as the front door on obsmage's drawing; the demo splits an invented setup into atoms and joins it back byte for byte | `site/`, `site/README.md` |

## Evidence: R4, the core plugin loads (2026-11-01)

Observed on gw33 (Ubuntu 26.04.1, `obs-studio 32.1.0-0ubuntu3` from apt). The plugin came out of the
add-on `.deb` (`dpkg-deb -x`, not installed) and was copied into a throwaway user plugin folder under
a temporary `HOME`; OBS ran under `xvfb-run` with `--multi --verbose` for 35 seconds, then stopped
on SIGTERM (log shows "Shutting down"). Lines from the OBS log of that run:

    17:54:25.181: Using EGL/X11
    17:54:25.715: Loading module: obsmage-core.so
    17:54:25.715: [obsmage-core] version 0.0.1
    17:54:25.715:   Loaded Modules:
    17:54:25.715:     obsmage-core.so
    17:54:25.828: [obsmage-core] loaded; display-binding audit runs here (read-only)

The second plugin line is the `OBS_FRONTEND_EVENT_FINISHED_LOADING` callback, so the frontend API
calls worked. Not shown by this run: that the two Tools-menu entries appear (a headless run has no
screenshot of the menu) and that clicking them works. Other modules in the same log failed for
reasons unrelated to us (decklink, obs-nvenc: no such hardware on a VM).

## Evidence: R4 and R9 on gw33 (2026-11-03, UTC)

The heal at `c6218a5` built the package with its tests inside (43 Python tests; e2e 11/11; healer
41/41; load check 6/6), and the user unit then ran `omg-load-check` by itself (`OnSuccess=`):

    00:25:10.519: Loading module: obsmage-core.so
    00:25:10.519: [obsmage-core] version 0.0.1
    00:25:10.665: [obsmage-core] loaded; display-binding audit runs here (read-only)
    omg-load-check: obsmage_0.0.1_amd64.deb loaded in OBS Studio - 32.1.0-0ubuntu3 after 1s

Nothing was left running and no throwaway HOME was left. `omg-dist` then staged
`obsmage-0.0.1-20261103-002239-c6218a53f11f.tar.gz` (sha256 `2f4ee5e1…3afd40`) and
`obsmage_0.0.1+git20261103.002239.c6218a5_amd64.deb` (sha256 `e3d6f77e…42393d`); a second, clean
build of the same commit in another folder gave both files byte for byte.

## Evidence: R1, Windows, the shortest path (2026-11-04, UTC)

GitHub Actions run 41825389557 (https://github.com/inputloop/obsmage/actions/runs/41825389557) at
`2f60d46`. The Linux job built `obsmage-0.0.1-20261104-115914-2f60d465c329-windows-x64-setup.exe`
(sha256 `ec90f120…88de0cdb`) and `.zip` (sha256 `4cc6dc40…dae0f834`); a build of the same commit on
another machine gave both byte for byte. `tests/e2e-windows.sh`: 12 ok; `--prove-red`: each check green
alone, then 16 planted faults, each red.

For each of OBS Studio 32.1.0 and 33.0.1, installed by its own installer (sha256 as pinned, fetched from
the GitHub release) into `C:\Tools\OBS Studio`, which both registry views then named: our installer
refused an empty folder (exit 2, nothing written), then, given no folder, installed there by itself, all
seven files byte for byte with the zip. libobs loaded the plugin from there (`obs_load_check.py`):

    obs_load_check: libobs 33.0.1 from C:\Tools\OBS Studio\bin\64bit
      libobs debug   Loading module: obsmage-core.dll
      libobs info    [obsmage-core] version 0.0.1
      ok   opened (MODULE_SUCCESS)
      ok   its locale answered from C:\Tools\OBS Studio\data\obs-plugins\obsmage-core (b'obsmage: compose screen maps')
    obs_load_check: LOADED

and OBS Studio itself (`obs64.exe`, on the runner's Microsoft Basic Render Driver through D3D11) logged:

    12:01:27.155: Loading module: obsmage-core.dll
    12:01:27.155: [obsmage-core] version 0.0.1
    12:01:27.424: [obsmage-core] loaded; display-binding audit runs here (read-only)

(33.0.1; 32.1.0 the same at 12:01:34–35). The uninstaller then left the OBS folder exactly as a snapshot
taken before our install (2245 entries on 32.1.0, 2404 on 33.0.1), and both checkers' prove-red went red
on a planted installer. Not shown: the wizard pages on a screen (every Windows run here was silent), and
what SmartScreen says on a person's machine.

## Additions proposed by Mentat (not yet blessed)

- **P1 — one source per display, bound by stable id.** The composer adds the stable id to any
  index-bound capture and keeps the index for older OBS. This removes the most common cause of a
  scene that quietly shows the wrong monitor after a re-plug. (Seen in Corwin's own collection:
  8 of 12 captures bound by index.)
- **P2 — calibration as atoms.** A calibration is versioned and diffable like any setting
  (`docs/AR-CONTROL.md`).
- **P3 — a preview diff before every write.** Every tool that changes a live OBS file prints a
  words-first diff and writes only with `--write`, leaving a dated backup beside the file.
- **P4 — the screen-map seed.** `omg_compose.py infer-layout` reads a person's hand-made screen
  map and uses it as their physical layout. Their own arrangement teaches the composer; no tape
  measure needed.

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin; claude-opus-5-5)
