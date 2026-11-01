# obsmage conventions

The house rules for every file in this tree. They are short on purpose. If a rule here stops
helping, change it here first, then change the code.

## What obsmage is

obsmage **is** OBS Studio: a downstream build that owns the whole OBS configuration, plus a set of
plugins that also install into an upstream OBS someone built themselves. Two kinds of code follow
from that:

- **The app** owns the full configuration: every profile, every scene collection, every key,
  credentials included. Atoms are pulled together into live OBS files and split back out. The
  round trip must be lossless (byte-exact for INI; parse-equal for JSON).
- **Feature tools and plugins** read only the atoms they need. A narrow tool is cheap because the
  atom layer already did the joining and splitting.

## Atoms (key/value normalization)

- An atom is one key and its raw string value, addressed by a path:
  `<stage>/<file>/<set>/<key>`, e.g. `profile/GSUS_Tech/basic.ini/Video/BaseCX`.
- A **stage** is a profile or a scene collection. A **set** is an INI section, or one source in a
  scene collection. A **scene** is an OBS scene (itself a source of type `scene`).
- Atoms live in `atoms/` as one `.kv` file per set: `atoms/<stage>/<file>/<set>.kv`, lines of
  `key=value` in the original order. Taxemes are directories; dates go in the journal, never in an
  atom path.
- Every atom has a **class**: `plain`, `path` (machine-local), `device` (hardware-bound) or
  `secret`. Secret atoms keep their values in the live configuration (and the local vault
  `.omg/vault.kv`, git-ignored, mode 600). Anything published (atoms in git, STAGES.md, the
  journal) shows only `@secret(len=N)`. The value never appears there.

## The roll-up: STAGES.md

`STAGES.md` is the single-file view of every atom: generated from `atoms/`, editable by hand, and
unrolled back into `atoms/`. It is a **seam**: two readers (a person, a tool) and two writers (the
app, a person) can work on either side. Its header carries a **pin** (the sha256 of the atoms it
was rolled from). If both sides changed since the pin, the tool stops and says which atoms
conflict. It never picks a side.

## Gradual centralization

Atoms that change together may later be stored near each other. That move is **never automatic**.
`omg suggest` reports co-change clusters from `ledger/changes.tsv`. A person decides, and the
journal records the decision. Obvious patterns are for the instrument to raise, not for the tool to
act on.

## Code

- Tools: Python 3 standard library only, under `tools/`. POSIX `sh` for service and build glue.
- Every test harness has a `--prove-red` mode (or a test that plants a fault) to show it can fail.
- Tests come in at least two languages: Python `unittest` in `tests/`, plus a POSIX `sh`
  end-to-end runner `tests/e2e.sh` against `tests/SPEC.txt`.
- Never write a user's live OBS files in place without `--write`, and always leave a dated backup
  beside them.
- Never delete a user's source or scene item: hide it and say so.

## Files and names

- Journal: `journal/YYYY/MM/DD/<slug>.md`. The date lives in the path, so it is findable.
- Licence lines go at the end of a file: code `GPL-3.0-or-later OR LGPL-3.0-or-later`, prose
  `CC-BY-SA-4.0`.
- Holder: `Copyright 2026 INPUTLOOP`. Byline in the BY (FOR AS) form, e.g.
  `Mentat (for Corwin; claude-opus-5-5)`.

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin; claude-opus-5-5)
