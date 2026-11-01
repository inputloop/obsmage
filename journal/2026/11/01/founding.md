# 2026-11-01 — founding

**Asked (Corwin, 01:24 CT):** a bespoke multiplatform OBS. A literate taxonomy over the whole
configuration, our own features as plugins, a build healer, AR desktop control, and a multi-head
auto-composer for the screen-map scenes he keeps by hand and finds very hard to keep up.

**Turned (01:33):** obsmage *is* OBS. It owns the whole configuration, credentials included.
Feature tools read only the atoms they need. So credentials are not stripped on import. They
become `secret`-class atoms: live in the profile and a local vault, `@secret(len=N)` everywhere
published.

**Observed** (receipts in the session):
- His GSUS Tech profile, his active collection and his 2024 Avalon collection split into
  ~27,800 atoms and join back losslessly, with 4 credentials withheld
  (`omg_atoms.py verify`, 0.3 s).
- Avalon collection: 12 monitor captures. **8 bind by index, 3 by stable id, 1 unbound** (reads
  as monitor 0). Mentat first said "9 of 12"; the composer's audit corrected it, and the tests
  assert 8/3/1. Index binding is why the screen maps drift when a display is re-plugged.
- Two bugs found by our own tests on day one: ledger events collided within one second, and
  rollup crashed on a bare file name (now SPEC AT10).

**Judged:** the composer ships first because it needs no camera. AR control stays at design until
calibration exists. Writing it down first keeps us from claiming a gesture we cannot test.

**Where the work ran:** in the cloud workspace for this repo; on AVALON for anything touching
his shelf (skills, transcripts, the h/ register, the books). All seven reachable ghostwheel
nodes answered (gw4, 7, 10, 15, 19, 26, 33), but none holds the seat or the keys this work
needed, so none was used. gw11 is out of bounds by his word.

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin; claude-opus-5-5)
