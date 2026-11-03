# 2026-11-02 — obsmage.com, the pipeline, and a test instance that keeps checking

**Asked (Corwin, 17:27 CT):** heal the web server and the test instance (obsmage.com had just been
pointed at gw33); then the distribution pipeline; then "a mint of our cloud with itself": a
single-user demo in the browser that shows the rest of the toolchain. Read by c4
`q/2026-11-02-obsmage-and-resume/READINGS.md`, S7 and S8, reading 1 of each. At 17:44 he made this
repository and obsmage-corwin public, which opened the releases.

**Observed on gw33 before anything changed:**
- nginx answered obsmage.com with its default page (no server block named it); https had no
  certificate for it (the request fell to another site's).
- The healer's user timer was healthy: it last ran at 00:11 UTC, said "up to date" at `c0ee528`, and
  `c0ee528` was GitHub's main. Its key is a deploy key held by the mirror (`core.sshCommand`).
- The test instance was not an instance: R4 had been shown once, on 11-01, by a script in a
  temporary HOME, and that run's 35-second `timeout` stopped only its direct child, so an `obs`
  process was still listed when it ended. None was running when this work began.

**Done, and why:**
- `omg-load-check` and a user unit the heal service starts after every good run: the plugin is
  loaded in the host's OBS in a throwaway HOME, the whole process group stopped after (dash's `kill`
  takes `kill -TERM -PGID`, not `kill -TERM -- -PGID`: the first try failed silently behind `2>/dev/null`).
- `omg-dist`: reproducible tarball and Debian package per commit, a credential scan on every bundle,
  `SHA256SUMS`, a channel/1 feed written last. A daily user timer on gw33 stages into
  `/var/lib/obsmage-dist/`.
- `site/`: obsmage.com, built like corwin.cloud, live with TLS. The demo's JavaScript atom layer is
  held to `omg_atoms.py` on 139 vectors, byte for byte.
- `omg_atoms`: obs-websocket's `ServerPassword` was classed plain (the rule knew `server_password`
  only). It is a secret now (AT11). obsmage-corwin's history holds no such key.

**Got past our tests, then caught:** the load check's own test (L6, "no OBS here") pruned PATH and
so ran gw33's real `/usr/bin/obs`; the package build at `4984ad0` failed there. The OBS command is
now named (`LOAD_OBS`), and the fix was checked with an OBS look-alike late on PATH (`c6218a5`).

**Judged:** releases open by one line in `site/site.conf`, kept as a switch so they can be closed
again; the bundles are not signed yet (the feed has the slot).

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin, claude-opus-5-5)
