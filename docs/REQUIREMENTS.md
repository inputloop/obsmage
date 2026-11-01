# obsmage requirements

Corwin's requirements (2026-11-01), each with where it stands. **Built** means code and tests are
in this tree. **Designed** means a document says how. **Open** means neither yet.

| # | Requirement | State | Where |
|---|---|---|---|
| R1 | A bespoke multiplatform OBS (Linux, Windows, macOS) | Designed | `docs/PACKAGING.md` |
| R2 | Distribution packaging first. Carry our patches in-tree against upstream versions; prefer what upstream already does well; offer patches upstream when ready, while still using our own copy | Designed | `docs/PACKAGING.md`, `packaging/` |
| R3 | A literate taxonomy over OBS configuration: a total wrap on the OBS API and config | Built (config); Open (API) | `tools/omg_atoms.py`, `STAGES.md`, `CONVENTIONS.md` |
| R4 | Our own features as OBS plugins | Skeleton (not built) | `plugin/obsmage-core/` |
| R5 | A decomposed-tree distribution setup, plus a system-service healer for regular Debian and source builds. Optional pull before build. Follow modes: tagged+signed, tagged, project meta, or main (**main is the default**) | Built | `packaging/healer/omg-heal`, `tests/e2e-healer.sh` |
| R6 | A physical-space-to-graphical-space map (a local service: ours, or bring your own) | Designed | `docs/AR-CONTROL.md` |
| R7 | AR desktop control mode. Releases on context menu, Start menu, ESC, Space or any click. Needs 2+ cameras and calibration reachable from the OBS UI with only the core plugin loaded | Designed | `docs/AR-CONTROL.md` |
| R7.1 | Magic hand | Designed | ″ |
| R7.2 | Flick to fill | Designed | ″ |
| R7.3 | Magic wand | Designed | ″ |
| R7.4 | Wall grab | Designed | ″ |
| R7.5 | Multi-head scene detector and auto-composer | **Built** (tool); plugin wiring Open | `tools/omg_compose.py`, `docs/COMPOSER.md` |
| R8 | No telemetry or feedback-loop work in this phase | Held | (decision, 2026-11-01) |

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
