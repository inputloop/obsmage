# 2026-11-04 — Windows, the shortest path: an unsigned installer for an OBS Studio you already have

**Asked (Corwin):** 2026-11-03 18:13 CST, people are curious "how close we are to seeing a Windows binary
installer build pipeline for OBSmage"; 2026-11-04 04:32 CST, "OSBMage on Windows: shortest path then full
bespoke" and "start unsigned". The bespoke Windows build of OBS itself is written down
(`docs/PACKAGING.md`), not built.

**Observed before choosing:**
- The plugin compiles cleanly with MinGW-w64 (GCC 13, `-Wall`) against OBS Studio 32.1.0's own headers,
  once `obsconfig.h` is generated from its template; it calls nine OBS functions (`nm -u`), all of them
  in the export tables of the real `obs.dll` and `obs-frontend-api.dll` of both OBS 32.1.0 and 33.0.1
  (`objdump -p` on the official Windows zips).
- libobs refuses a module built for a newer major.minor (`obs-module.c`), so building against 32.1 reaches
  32.1 and later.
- OBS Studio 33 moved its own plugins to `core\<name>\`; its plugin manager still loads
  `obs-plugins\64bit\` and `data\obs-plugins\<name>\` relative to the program
  (`PluginModuleLoader_Windows.cpp`, "legacy root path"). 33 has neither folder of its own, so our
  uninstaller removes them when they are empty.
- OBS Studio's installers (32.1.0, 33.0.1) are NSIS, so CI can install them silently; the script that
  builds them is not in obs-studio's tree, so where they record the install folder is checked by running
  them in CI, not read from source.

**Done, and why:**
- `packaging/windows/omg-win`: one commit in, an installer and a zip out, each with its `.sha256`; MinGW-w64
  and NSIS, both free software, so it runs on Linux beside omg-dist and is tested here. The same commit
  gives the same bytes.
- The installer finds OBS Studio (registry, then Program Files) and lets the person browse when it cannot;
  it refuses a folder without `obs64.exe`; its licence page offers the GPL without an "I agree".
- One version: the plugin's version string now comes from CMake, and omg-win refuses to build when
  `CMakeLists.txt` and `debian/changelog` disagree.
- Checks: `tests/e2e-windows.sh` (sh), `tests/windows_pe_check.pl` (Perl), and on Windows
  `.github/workflows/windows.yml` with `packaging/windows/installer_check.py` and `obs_load_check.py`.

**Got past our tests, then caught (CI, three runs):**
- Run 1 (`5f11d55`): W5 went red on the runner only. Its awk is gawk, which drops `\o` from a `-v`
  value, so the NSIS data folder lost its backslashes; here awk is mawk. Backslashes now become slashes
  before awk, and W5 reads the script with every awk at hand. Fixing it showed that W5 run alone was red
  with nothing planted (it read a list only W4 made), so its plants could have gone red for that reason:
  `--prove-red` now runs each check alone, unplanted, and requires green first (`a13830f`).
- Run 2 (`a13830f`): all held on 32.1.0, and OBS itself logged the plugin loaded; on 33.0.1 the
  uninstall check went red. OBS 33's installer makes an empty `obs-plugins\`, and our uninstaller, removing
  that folder when empty, would have deleted something OBS made. The installer now records which plugin
  folders it made, and the uninstaller removes only those; CI compares OBS's whole folder with a snapshot,
  and a planted installer shows those checks fail (`2f60d46`).
- Run 3 (`2f60d46`, 41825389557): everything held on both. Evidence in `docs/REQUIREMENTS.md`.

**Judged:** the zip ships beside the installer for people whose machines refuse unsigned programs.
Publishing (omg-dist's feed, obsmage.com/dist) waits for Corwin's yes.

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin, claude-opus-5-5)
