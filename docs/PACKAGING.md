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

## The add-on package and the user timer

`debian/` at the repository root builds one package, `obsmage`: the `obsmage-core` plugin, the two
tools (`omg-atoms`, `omg-compose`) and the healer with its units. It needs OBS Studio only at run
time and touches nothing outside `/usr`, so `apt remove obsmage` removes all of it. Point `SRC` at
this repository and the healer builds it (it uses the tree's own `debian/`; the `DEBIAN` overlay is
only for an upstream tree that has none). Tests run inside the build.

`packaging/healer/user/` holds the same service and timer for one user without root
(`systemctl --user`); `NOTES.md` has the install lines and the undo. It is what runs on gw33.

## The test instance (2026-11-02)

`packaging/healer/omg-load-check` keeps requirement R4 ("loads") checked, not remembered. The user
heal service starts `obsmage-loadcheck.service` after every good run (`OnSuccess=`): the newest
`obsmage_*.deb` in `WORK` is unpacked (never installed), its `obsmage-core.so` copied into a throwaway
HOME as a user plugin, OBS Studio started under `xvfb-run` in its own process group, and the log read
until the plugin's "loaded" line (at most `LOAD_SECS`, 60). Then the whole group is stopped and the
HOME removed. `WORK/state/load-check` holds the last result, `load.tsv` every one. Exit 0 loaded, 1
not, 3 a tool is missing. `tests/e2e-loadcheck.sh` checks it against a fake OBS that leaves a child
behind.

## The distribution pipeline (2026-11-02)

`packaging/dist/omg-dist` builds, from one commit (default: `main` of the healer's mirror), a source
tarball `obsmage-<version>-<stamp>-<rev12>.tar.gz` (`git archive` through `gzip -n`: the same commit
gives the same bytes; the stamp is the commit's time) and, when `dpkg-buildpackage` and the build
dependencies are present, the Debian package `obsmage_<version>+git<stamp>.<rev7>_<arch>.deb` (a
snapshot changelog entry made from the commit, built with `SOURCE_DATE_EPOCH` set to the commit time).
Every bundle passes `packaging/dist/secret-scan.py` first: a credential in an atom store must read
`@secret(len=N)`, and nothing shaped like a live key may appear (lines saying FAKE excepted, as this
tree marks its test credentials). Then it stages, into `DIST_OUT/public/`, the bundles, one record per
release, `SHA256SUMS`, and last the channel feed `channel.json` (channel/1, the line form of c4's
`d/channels/SPEC.md` and about-corwin's feed, with obsmage's `deb`, `deb_sha256` and `deb_size`),
checked by `packaging/dist/chan_check.py` before it replaces the old one. It keeps 20 releases (never
fewer than 3) and does nothing when the commit has not moved. On gw33 it runs as a user timer
(`packaging/dist/user/`, daily after the healer), staging into `/var/lib/obsmage-dist/`; nginx serves
`public/` at https://obsmage.com/dist/ while `site/site.conf` says `releases: open`.
Checked by `tests/e2e-dist.sh` (sh) and `tests/test_dist.py` (Python); `--prove-red` plants nine faults.

## Windows: the shortest path (2026-11-04)

Corwin, 2026-11-04: "OSBMage on Windows: shortest path then full bespoke" and "start unsigned". The
shortest path puts obsmage into an OBS Studio the person already has; it does not build OBS.

- **Route.** `packaging/windows/omg-win` (POSIX sh, on any Linux host) cross-builds `plugin/obsmage-core`
  with MinGW-w64 by the plugin's own `CMakeLists.txt`. Its two `find_package` calls are answered by
  `packaging/windows/sdk/`: OBS Studio's own headers at the commit pinned in `pins.env` (tag 32.1.0; only
  `libobs/` and `frontend/api/` are fetched), and import libraries that `dlltool` makes from `obs.def` and
  `obs-frontend-api.def`, which name the nine OBS functions the plugin calls. Why not MSVC on a Windows
  runner, the way obsproject's plugin template builds: this way it builds and is tested on Linux (here,
  and on gw33 beside omg-dist), it needs no OBS download to build, and every tool in it is free software
  (GCC, binutils, NSIS). A Windows machine is needed only to show the plugin loads.
- **New calls into OBS.** One fails the link ("undefined reference") until its name is added to the .def
  file. The tests check that every name there is an `EXPORT` in OBS's headers at the pin; CI loads the
  plugin into the real `obs.dll`.
- **Which OBS.** libobs refuses a module built for a newer major.minor, so a plugin built against 32.1
  loads in OBS Studio 32.1 and later. CI loads it in 32.1.0 and 33.0.1.
- **Layout (installer).** `obs-plugins\64bit\obsmage-core.dll` and `data\obs-plugins\obsmage-core\` (locale,
  `tools\`, `COPYING`, `COPYING.LESSER`, `README-windows.txt`, the uninstaller) inside the OBS Studio folder.
  OBS 32 loads plugins from there; OBS 33 still does, but its Plugin Manager marks them "Legacy", and
  obsproject's knowledge base says that folder is not loaded from OBS 34.0 on.
- **Layout (zip, 2026-11-06).** OBS 33's per-plugin layout, one folder to drop into
  `%ProgramData%\obs-studio\plugins\`: `obsmage-core\obsmage-core.dll` and `obsmage-core\data\` (the same
  files as the installer's `data\obs-plugins\obsmage-core\`, less the uninstaller). The source is OBS 33.0.1's
  `frontend/plugin-manager/PluginModuleLoader_Windows.cpp` (unchanged on master 7a25c3f): the Root Path is
  `<ProgramData>/obs-studio/plugins/<Plugin>/<Plugin>.dll` with `.../<Plugin>/data`; its legacy paths are the
  OBS folder's `obs-plugins/64bit/` and `ProgramData\...\<Plugin>\bin\64bit\`, the layout OBS 32 used
  (32.1.0's `frontend/widgets/OBSBasic.cpp`, `AddExtraModulePaths`). OBS 32 does not read the flat layout,
  so the zip is for OBS 33 and later and the installer stays as it was, for 32.1 and later. See also
  https://obsproject.com/kb/legacy-plugin-developer-info. Checked by `tests/e2e-windows.sh` W13 (and its two
  plants) and `tests/test_windows_py38.py` ZipLayout; on Windows, `installer_check.py installs` reads the
  zip through `in_obs_dir`, and on OBS 33 the workflow drops the zip into ProgramData and starts OBS (a
  witness, like the obs64.exe step).
- **Not yet (the installer).** Writing to `%ProgramData%\obs-studio\plugins\obsmage-core\` on OBS 33 and
  later, and removing an older copy from the OBS folder as it does, which the knowledge base asks of
  installers. That needs the installer to tell OBS 32 from 33 (32 reads only `bin\64bit\` there).
- **Finding OBS Studio.** The folder its installer records (`HKLM\SOFTWARE\OBS Studio`, 32-bit view, then
  64-bit), then `%ProgramFiles%\obs-studio`; otherwise the folder page says it was not found and the
  person browses. A folder without `bin\64bit\obs64.exe` is refused: in the wizard Next stays off;
  silently (`/S`) it exits 2 and writes nothing.
- **The installer.** NSIS 3 (zlib licence; OBS Studio's own installer is NSIS too). The licence page
  presents the GPL as what it is: no "I agree", only Next. Unsigned: SmartScreen warns, and the person
  chooses "More info", then "Run anyway". It adds an entry to Settings, Apps, in which it records which
  of OBS's plugin folders it had to make (OBS 33 has an empty `obs-plugins\` and no `64bit\` or
  `data\obs-plugins\`). The uninstaller removes its files by name, and only those folders, only when
  empty; OBS Studio's folder is left as it was before the install, and its settings are not touched.
- **The same shape as omg-dist.** The version is debian/changelog's (the plugin's `CMakeLists.txt` must
  agree, and the plugin's version string comes from CMake). Names come from the commit:
  `obsmage-<version>-<stamp>-<rev12>-windows-x64-setup.exe` and `.zip`, each with a `.sha256` beside
  it. `secret-scan.py` passes over the whole stage before the installer and the zip are made from it.
  The build is reproducible: two builds of a commit give the same bytes, and a rebuild that differs from
  what is staged fails the run.
- **Checked by** `tests/e2e-windows.sh` (sh; `--prove-red` plants a fault for each check) and
  `tests/windows_pe_check.pl` (Perl, reads the DLL itself); on Windows by `.github/workflows/windows.yml`,
  which installs OBS Studio 32.1.0 and 33.0.1 with their own installers into a non-default folder, then
  runs `packaging/windows/installer_check.py` (refuses a non-OBS folder, finds OBS by itself, installs the
  zip's bytes, uninstalls back to a snapshot of OBS's folder) and `packaging/windows/obs_load_check.py`
  (libobs loads the plugin from where it went), each with a prove-red, and starts `obs64.exe` as a witness.
- **Not yet:** wiring into omg-dist's feed and obsmage.com/dist (Corwin's yes), signing, ARM64, a
  per-user install without administrator rights.

## Windows: the bespoke build (later; written down, not built)

What "obsmage IS OBS" would take on Windows:

1. **OBS Studio from source.** MSVC (Visual Studio 2022) with obs-studio's CMake preset `windows-x64`;
   upstream does not build OBS itself with MinGW. obs-deps and Qt 6 come as prebuilt archives that
   obs-studio's `buildspec.json` already pins by hash, or we build obs-deps ourselves and pin our own
   commit. Each build is long; OBS's own CI caches the dependencies, and ours would need to as well.
2. **Our patch queue on Windows.** `patches/<version>/` applied as omg-heal applies it on Linux; the
   healer is POSIX sh, so on Windows it needs Git for Windows' sh or a port.
3. **The app owns its configuration.** obsmage-core and later plugins built in-tree, OBS run in portable
   mode (`config\` beside the app) so the whole configuration is obsmage's atoms, and a distinct folder
   and registry key so it can sit beside an upstream OBS Studio.
4. **Our installer for the whole app.** OBS's installer script is not in obs-studio's tree (we did not
   find it under `frontend/` or `cmake/windows/` at 33.0.1), so ours grows from `obsmage.nsi`, with an
   uninstaller and updates from the channel feed (OBS's own updater off or pointed at ours).
5. **Separate pins with their own terms:** the hardware encoders (NVENC, AMF, QSV) and the browser source
   (CEF, large; its redistribution terms need reading first).
6. **Signing becomes pressing.** An unsigned full OBS trips SmartScreen and antivirus far harder than a
   small plugin installer. The options are a code-signing certificate held in hardware or a cloud signer,
   or a free signing service for free software projects (SignPath Foundation offers one). The channel
   feed already has a signature slot.
7. **Tests.** The load check grows into OBS's own test suite plus an `obs64.exe` run on a runner;
   reproducibility needs MSVC's `/Brepro` and care with PDB paths.

## Limits

The healer packages but does not install build dependencies, sign packages, or publish them; omg-dist
stages them for nginx and does not sign them either (a signature slot is in the feed's spec). omg-win
stages the Windows installer and zip and signs nothing.
Submodules are not checked out. `--dry-run` still runs read-only git queries. The `meta` mode
reads the first `project(...)` call in `CMakeLists.txt`; a version given by a variable is not
resolved.

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin; claude-sonnet via subagent)
