# 2026-11-06 — the Windows zip in OBS Studio 33's per-plugin layout

**Asked (Corwin, through the session that briefed this one):** OBS Studio's Plugin Manager on Avalon marks
obsmage-core "Legacy: This plugin is installed to a location that will stop working in the future"; make the
Windows package and its install notes use OBS's current per-plugin layout, with a check that can fail.

**Observed:**
- OBS 33.0.1, `frontend/plugin-manager/PluginModuleLoader_Windows.cpp` (the same on master at 7a25c3f): the
  Root Path is `C:/ProgramData/obs-studio/plugins/<Plugin>/<Plugin>.dll` with data in `.../<Plugin>/data`.
  Its *legacy* paths are the OBS folder's `obs-plugins/64bit/` + `data/obs-plugins/<Plugin>`, and
  `ProgramData/obs-studio/plugins/<Plugin>/bin/64bit/`. So the `bin\64bit\` layout the brief expected is
  itself flagged Legacy by 33.
- OBS 32.1.0, `frontend/widgets/OBSBasic.cpp` `AddExtraModulePaths`: ProgramData is read only as
  `<Plugin>/bin/64bit/`. 32 does not read the flat layout.
- obsproject.com/kb/legacy-plugin-developer-info: the OBS-folder location is not loaded from OBS 34.0 on;
  authors should "update their installers or zip distributions for the ProgramData structure".

**Done:** the zip now holds `obsmage-core/obsmage-core.dll` and `obsmage-core/data/...`, to drop into
`%ProgramData%\obs-studio\plugins\` (OBS 33 and later). The installer is unchanged (OBS folder, 32.1 and
later). README-windows.txt says both, and how to remove a hand-placed legacy copy. Checks: e2e-windows W13 +
two plants; test_windows_py38 ZipLayout + its plant; the Windows workflow maps zip names through
`installer_check.in_obs_dir` and, on 33, drops the zip into ProgramData and starts OBS.

**Open (Corwin's call):** the installer writing to ProgramData on 33 and later, telling 32 from 33.

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin, claude-opus-5-5)
