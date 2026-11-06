obsmage @VERSION@ for Windows x64, inside your OBS Studio

What this is
  obsmage-core, a plugin for OBS Studio. It adds two entries to the Tools menu; for now they only
  write a line to OBS Studio's log. Beside it, two command line tools:
    tools\omg_atoms.py    splits an OBS configuration into atoms and joins it back, losslessly
    tools\omg_compose.py  the multi-monitor composer
  The tools need Python 3.8 or later (standard library only). Try:
    py "%ProgramData%\obs-studio\plugins\obsmage-core\data\tools\omg_atoms.py" find
  Built against OBS Studio @OBS_TAG@; it loads in OBS Studio @OBS_TAG@ and later.

Where it goes: from the zip (OBS Studio 33 and later)
  The zip holds one folder, obsmage-core. Put that whole folder into
    C:\ProgramData\obs-studio\plugins\
  (make the plugins folder if it is not there; ProgramData is hidden, so type the path into
  Explorer's address bar). You should then have
    C:\ProgramData\obs-studio\plugins\obsmage-core\obsmage-core.dll
    C:\ProgramData\obs-studio\plugins\obsmage-core\data\    this file, the locale, the tools, the licences
  This is the place OBS Studio 33 looks for plugins first. OBS Studio 32 does not look there:
  on OBS Studio 32, use the installer instead.

Where it goes: from the installer (OBS Studio @OBS_TAG@ and later)
  The installer writes into your OBS Studio folder:
    obs-plugins\64bit\obsmage-core.dll
    data\obs-plugins\obsmage-core\    this file, the locale, the tools, the licences, the uninstaller
  OBS Studio 33 still loads it from there, but its Plugin Manager marks it "Legacy": OBS says
  that folder stops working in a later version (34.0). To move to the new place, uninstall it
  (below), then use the zip as above.

Moving an older copy by hand
  If you put an earlier obsmage into your OBS Studio folder by hand (not with the installer),
  close OBS Studio, then delete these two from the OBS Studio folder
  (usually C:\Program Files\obs-studio):
    obs-plugins\64bit\obsmage-core.dll
    data\obs-plugins\obsmage-core        (the whole folder)
  then put the zip's obsmage-core folder into C:\ProgramData\obs-studio\plugins\ as above.
  Keep only one copy of obsmage-core.

Not signed
  This build is not code-signed. Windows SmartScreen warns about the installer: choose
  "More info", then "Run anyway". Check the download against the sha256 published beside it first.

To remove it
  From the zip: delete the folder C:\ProgramData\obs-studio\plugins\obsmage-core.
  From the installer: Settings, Apps, Installed apps, obsmage; or run uninstall-obsmage.exe in
  this folder. It removes only the files it wrote. Your OBS Studio and its settings stay as they are.

Licence and source
  obsmage's code: GPL-3.0-or-later OR LGPL-3.0-or-later (COPYING and COPYING.LESSER, beside this file).
  Source: https://github.com/inputloop/obsmage at commit @REVISION@
  (as one file: @SOURCE_TARBALL@, made by packaging/dist/omg-dist from the same commit).
  Built with MinGW-w64 against OBS Studio's own headers (GPL-2.0-or-later), from
  https://github.com/obsproject/obs-studio at commit @OBS_COMMIT@ (tag @OBS_TAG@).

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin, claude-opus-5-5)
