# Packaging and the healer

obsmage builds Debian packages and source tarballs from a decomposed tree, and a small service,
the healer, keeps those builds current. This page says what is where, how the healer decides
what to build, how we carry patches, and what it writes down.

## The decomposed tree

    patches/<upstream-version>/series, *.patch   our patch queue against upstream releases
    packaging/debian/                            debian/ overlay (see packaging/debian/README.md)
    packaging/healer/omg-heal                    the healer (POSIX sh)
    packaging/healer/obsmage-heal.{service,timer}  systemd units; NOTES.md covers cron hosts
    packaging/healer/heal.conf.example           the config, KEY=VALUE
    tests/e2e-healer.sh                          end-to-end test (also shows itself red)

The upstream source stays pristine. Our changes are the patch queue, the debian overlay, and
the obsmage plugins; the healer joins them to an upstream checkout at build time.

## Follow modes

`FOLLOW` in the config chooses which upstream ref gets built. `omg-heal plan` says in plain
words what it would pick and why, with no side effects.

| FOLLOW | Builds | Notes |
|---|---|---|
| `main` (default) | tip of `BRANCH` (the remote's default branch unless set) | needs no tags |
| `meta` | the tag for the version declared in the tree | reads `VERSION`, else CMake `project(... VERSION x.y.z)`, at the tip of `BRANCH`; finds `vX.Y.Z` or `X.Y.Z`; no tag means "not released yet, not building" (exit 5) |
| `tagged` | newest release-looking tag by version order | prereleases such as `-rc1` are included |
| `tagged+signed` | as `tagged`, if `git verify-tag` passes against `KEYRING` | unsigned or badly signed: REFUSED (exit 4); it does not fall back to an older tag |

`PULL=yes` (default) keeps a mirror at `WORK/src.git` and fetches before each build; `PULL=no`
uses what is already there (a local `SRC` directory is read in place).

## Carrying patches against upstream

The queue for upstream version X lives in `patches/X/series` (quilt style: one patch per line,
optional `-pN`, `#` comments). The healer detects X from the tag name, else from the tree's
version, checks the patches out of a clean tree and applies them in order. For every entry it
reports one of:

- APPLIED
- SKIPPED, already in upstream: the patch reverse-applies cleanly, so upstream has the change and
  upstream behaviour wins
- SKIPPED, file listed but missing
- FAILED: fits neither way; the build stops (exit 7) so we never ship something half-patched

No `patches/X/` directory means upstream is built as it is. We patch only when needed.

## From carried patch to upstream offer

1. A patch starts in `patches/X/`, with a header saying what it fixes and why configuration did
   not suffice.
2. When it is worth offering, send the same file upstream (as a pull request or patch). Nothing
   in our tree changes: we keep using our copy, so our builds do not wait on anyone.
3. When upstream merges it, the next release's build reports the patch as "already in
   upstream" and skips it. Delete the entry from the newer `series`, keeping older versions'
   queues as they were, because those releases still need them.
4. If upstream asks for changes, refresh our copy to match what we offered; the two should not
   drift apart.

## What the healer records

Under `WORK` (for the service, `/var/lib/obsmage-heal`):

- `src.git`: the mirror of `SRC`
- `build-<sha8>/`: the clean tree for that commit (replaced on rebuild)
- `<NAME>-<id>.tar.xz`: the pristine upstream source tarball (`git archive`); the patch queue
  travels separately. Debian packages from `dpkg-buildpackage -us -uc -b` land in `WORK`
- `state/last-build`: when, ref, sha, mode, result, follow mode (one `key=value` per line)
- `state/heal.tsv`: one line per `heal` run, tab separated: when, ref, sha, mode, result, where
  result is `ok`, `uptodate`, `build-failed`, `patch-failed`, `refused`, `no-ref`,
  `missing-tool` or `fetch-failed`
- `state/lock`: held while a run is active; a stale one from a dead process is removed

`omg-heal status` reads these back in words. `heal` builds when there is no record, the last
build failed, the followed ref moved, or `BUILD` changed; otherwise it logs `uptodate`. Its exit
code is the build's, so a failing run shows as a failed systemd unit.

## Limits

The healer packages but does not install build dependencies, sign packages, or publish them.
Submodules are not checked out. `--dry-run` still runs read-only git queries. The `meta` mode
reads the first `project(...)` call in `CMakeLists.txt`; a version given by a variable is not
resolved.

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin; claude-sonnet via subagent)
