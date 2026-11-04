obsmage @VERSION@ for Windows x64, inside your OBS Studio

What this is
  obsmage-core, a plugin for OBS Studio. It adds two entries to the Tools menu; for now they only
  write a line to OBS Studio's log. Beside it, two command line tools:
    tools\omg_atoms.py    splits an OBS configuration into atoms and joins it back, losslessly
    tools\omg_compose.py  the multi-monitor composer
  The tools need Python 3.8 or later (standard library only). Try:
    py "%ProgramFiles%\obs-studio\data\obs-plugins\obsmage-core\tools\omg_atoms.py" find
  Built against OBS Studio @OBS_TAG@; it loads in OBS Studio @OBS_TAG@ and later.

Where the files are, in your OBS Studio folder
  obs-plugins\64bit\obsmage-core.dll
  data\obs-plugins\obsmage-core\    this file, the locale, the tools, the licences, the uninstaller

Not signed
  This build is not code-signed. Windows SmartScreen warns about the installer: choose
  "More info", then "Run anyway". Check the download against the sha256 published beside it first.

To remove it
  Settings, Apps, Installed apps, obsmage; or run uninstall-obsmage.exe in this folder. It removes
  only the files listed above. Your OBS Studio and its settings stay as they are.

Licence and source
  obsmage's code: GPL-3.0-or-later OR LGPL-3.0-or-later (COPYING and COPYING.LESSER, beside this file).
  Source: https://github.com/inputloop/obsmage at commit @REVISION@
  (as one file: @SOURCE_TARBALL@, made by packaging/dist/omg-dist from the same commit).
  Built with MinGW-w64 against OBS Studio's own headers (GPL-2.0-or-later), from
  https://github.com/obsproject/obs-studio at commit @OBS_COMMIT@ (tag @OBS_TAG@).

Copyright 2026 INPUTLOOP; CC-BY-SA-4.0.
Mentat (for Corwin, claude-opus-5-5)
