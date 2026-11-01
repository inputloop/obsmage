# Debian packaging for obsmage

obsmage is OBS Studio plus our configuration layer, so the Debian packaging follows Debian's own
`obs-studio` source package as closely as we can and differs only where we must. The healer
(`packaging/healer/omg-heal`) builds this; see `docs/PACKAGING.md` for the whole picture.

## Layout

    packaging/debian/            the debian/ directory, overlaid onto an upstream tree at build time
      control  rules  changelog  copyright  source/format ...   (to be written; see below)
      patches/                   NOT hand-edited: generated from our queue, see next section
    patches/<upstream-version>/  our patch queue (repo root): series + *.patch, quilt style
    packaging/healer/            omg-heal and the systemd units

Following Debian's approach: `debian/source/format` is `3.0 (quilt)`, the upstream tree is kept
pristine (the `orig` tarball), and every change to upstream is a quilt patch. Debian maintains
`obs-studio` with `gbp` (git-buildpackage), `debian/gbp.conf`, `pq` (patch-queue) branches and
`dh` with `debhelper-compat`. We use the same tools so a maintainer who knows Debian's workflow
can read ours. Before copying anything, read the current Debian packaging for `obs-studio`
(`apt source obs-studio`, or the Debian salsa repository) and record the version you started
from here: `<DEBIAN-OBS-STUDIO-VERSION: look up with rmadison obs-studio>`.

## Where our patch queue lives

In the repository root at `patches/<upstream-version>/series`, one directory per upstream
release, plus the `.patch` files beside it. The healer applies the queue for the detected
upstream version to a clean checkout; the Debian build then sees the same files as
`debian/patches` (the overlay step copies or links the queue there; until that glue exists the
healer applies the queue to the tree itself and `dpkg-buildpackage` packages the patched tree).
Prefer upstream behaviour: add a patch only when something cannot be done by configuration, and
retire it when upstream has the fix (the healer reports "already in upstream" for those).

## Build by hand

    gbp buildpackage --git-ignore-new -us -uc -b     # on a gbp checkout, or
    omg-heal --conf heal.conf build                  # clean tree, queue applied, dpkg-buildpackage -us -uc -b

Packages are unsigned (`-us -uc`); signing is a separate, deliberate step by the release keeper.

## To fill in (placeholders, not guesses)

- Package version scheme: `<UPSTREAM-VERSION>-<OBSMAGE-REVISION>`; confirm epoch/suffix policy
  against Debian's `obs-studio` version `<LOOK UP: rmadison obs-studio>`.
- `Build-Depends`: copy from Debian's `debian/control` for the matching `obs-studio` version
  `<LOOK UP>`, then trim or add; do not trust a remembered list.
- Target suite and architectures: `<DECIDE>`.

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin; claude-sonnet via subagent)
