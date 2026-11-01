# obsmage requirements

Corwin's requirements (2026-11-01), each with where it stands. **Built** means code and tests are
in this tree. **Designed** means a document says how. **Open** means neither yet.

| # | Requirement | State | Where |
|---|---|---|---|
| R1 | A bespoke multiplatform OBS (Linux, Windows, macOS) | Designed | `docs/PACKAGING.md` |
| R2 | Distribution packaging first. Carry our patches in-tree against upstream versions; prefer what upstream already does well; offer patches upstream when ready, while still using our own copy | Designed | `docs/PACKAGING.md`, `packaging/` |
| R3 | A literate taxonomy over OBS configuration: a total wrap on the OBS API and config | Built (config); Open (API) | `tools/omg_atoms.py`, `STAGES.md`, `CONVENTIONS.md` |
| R4 | Our own features as OBS plugins | Skeleton; **compiles, links and loads** in OBS Studio 32.1.0 (Ubuntu 26.04, gw33, 2026-11-01; evidence below). Its menu entries are not yet clicked and do nothing but log | `plugin/obsmage-core/` |
| R5 | A decomposed-tree distribution setup, plus a system-service healer for regular Debian and source builds. Optional pull before build. Follow modes: tagged+signed, tagged, project meta, or main (**main is the default**) | Built. The healer built an obsmage add-on `.deb` of this repo on gw33 following `main` (2026-11-01) and runs there as a systemd user timer. A deb of OBS itself (upstream + patch queue) is **not** built: there is no patch queue and no `debian/` overlay for OBS yet | `packaging/healer/omg-heal`, `tests/e2e-healer.sh`, `debian/`, `packaging/healer/user/` |
| R6 | A physical-space-to-graphical-space map (a local service: ours, or bring your own) | Designed | `docs/AR-CONTROL.md` |
| R7 | AR desktop control mode. Releases on context menu, Start menu, ESC, Space or any click. Needs 2+ cameras and calibration reachable from the OBS UI with only the core plugin loaded | Designed | `docs/AR-CONTROL.md` |
| R7.1 | Magic hand | Designed | ″ |
| R7.2 | Flick to fill | Designed | ″ |
| R7.3 | Magic wand | Designed | ″ |
| R7.4 | Wall grab | Designed | ″ |
| R7.5 | Multi-head scene detector and auto-composer | **Built** (tool); plugin wiring Open | `tools/omg_compose.py`, `docs/COMPOSER.md` |
| R8 | No telemetry or feedback-loop work in this phase | Held | (decision, 2026-11-01) |

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
