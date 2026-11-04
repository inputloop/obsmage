; obsmage.nsi -- the obsmage installer for Windows x64 (the shortest path): it puts the obsmage-core plugin, its
; locale, the two Python tools and the licence texts into an OBS Studio that is already installed.
;
; Built by packaging/windows/omg-win with makensis (NSIS 3, zlib licence), which passes:
;   VERSION    the version, from debian/changelog (the one place it is kept)
;   VERSION4   the same as four numbers, for the Windows file properties
;   REVISION   the commit it was built from
;   STAGE      the staged tree, which the credential scan has passed; every File below comes from it
;   OUTFILE    where to write the installer
;
; Where OBS Studio is: the folder OBS Studio's own installer records in the registry (HKLM\SOFTWARE\OBS Studio,
; 32-bit view, then 64-bit view), then %ProgramFiles%\obs-studio; when neither holds bin\64bit\obs64.exe the
; folder page says so and the person browses to it. A folder without bin\64bit\obs64.exe is refused, in the
; wizard and silently (/S exits 2 and writes nothing).
; Layout: obs-plugins\64bit\obsmage-core.dll and data\obs-plugins\obsmage-core\, which OBS Studio 32 loads and
; OBS Studio 33 still loads (it calls this the legacy root path).
; Unsigned: Windows SmartScreen warns; the person chooses "More info", then "Run anyway".

Unicode true
ManifestDPIAware true
SetCompressor /SOLID lzma
RequestExecutionLevel admin

!include MUI2.nsh
!include LogicLib.nsh
!include x64.nsh

!ifndef VERSION | VERSION4 | REVISION | STAGE | OUTFILE
  !error "omg-win passes VERSION, VERSION4, REVISION, STAGE and OUTFILE"
!endif

!define DATA "data\obs-plugins\obsmage-core"
!define UNINST "Software\Microsoft\Windows\CurrentVersion\Uninstall\obsmage"
; in the uninstaller, $INSTDIR is the folder the uninstaller is in: <OBS Studio>\data\obs-plugins\obsmage-core
!define UN_OBS "$INSTDIR\..\..\.."

Name "obsmage ${VERSION}"
OutFile "${OUTFILE}"
BrandingText "obsmage ${VERSION}, unsigned"
ShowInstDetails show
ShowUninstDetails show

VIProductVersion "${VERSION4}"
VIAddVersionKey "ProductName" "obsmage"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "FileDescription" "obsmage installer (unsigned)"
VIAddVersionKey "CompanyName" "INPUTLOOP"
VIAddVersionKey "LegalCopyright" "Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later"
VIAddVersionKey "Comments" "Built from commit ${REVISION}"

Var Found

; Made KEY DIR VAR: VAR = 1 when this install makes $INSTDIR\DIR (or an earlier one into this same folder recorded
; that it did), else 0
!macro Made KEY DIR VAR
  ReadRegStr $R0 HKLM "${UNINST}" "InstallLocation"
  ReadRegDWORD ${VAR} HKLM "${UNINST}" "${KEY}"
  ${If} $R0 != $INSTDIR
  ${OrIf} ${VAR} != 1
    ${If} ${FileExists} "$INSTDIR\${DIR}\*.*"
      StrCpy ${VAR} 0
    ${Else}
      StrCpy ${VAR} 1
    ${EndIf}
  ${EndIf}
!macroend

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TEXT "This puts obsmage ${VERSION} into the OBS Studio already on this computer: the obsmage-core plugin and two Python tools.$\r$\n$\r$\nThis installer is not signed, which is why Windows may have warned you. obsmage is free software from INPUTLOOP; its source is at https://github.com/inputloop/obsmage.$\r$\n$\r$\nClose OBS Studio before you continue."
!insertmacro MUI_PAGE_WELCOME
!define MUI_LICENSEPAGE_TEXT_TOP "obsmage is free software. You do not have to accept this licence to install or run it: it gives you the right to share and change obsmage."
!define MUI_LICENSEPAGE_TEXT_BOTTOM "obsmage's code may also be used under the GNU LGPL (COPYING.LESSER, installed beside it). Press Next to continue."
!define MUI_LICENSEPAGE_BUTTON "$(^NextBtn)"
!insertmacro MUI_PAGE_LICENSE "${STAGE}\${DATA}\COPYING"
!define MUI_DIRECTORYPAGE_TEXT_TOP "$Found"
!define MUI_DIRECTORYPAGE_TEXT_DESTINATION "OBS Studio folder (the one that holds bin\64bit\obs64.exe)"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_TEXT "obsmage is in your OBS Studio. Start OBS Studio: its Tools menu now has two obsmage entries.$\r$\n$\r$\nTo remove obsmage, use Settings, Apps; your OBS Studio and its settings stay as they are."
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "obsmage needs 64-bit Windows and a 64-bit OBS Studio." /SD IDOK
    SetErrorLevel 2
    Abort
  ${EndIf}
  ${If} $INSTDIR != ""
    StrCpy $Found "You chose this folder."
    Return
  ${EndIf}
  ; 1. where OBS Studio's own installer records itself
  SetRegView 32
  ReadRegStr $0 HKLM "SOFTWARE\OBS Studio" ""
  SetRegView 64
  ${If} $0 == ""
    ReadRegStr $0 HKLM "SOFTWARE\OBS Studio" ""
  ${EndIf}
  ${If} $0 != ""
  ${AndIf} ${FileExists} "$0\bin\64bit\obs64.exe"
    StrCpy $INSTDIR $0
    StrCpy $Found "OBS Studio is where its installer recorded it (in the registry). Choose another folder only if you use a different OBS Studio."
    Return
  ${EndIf}
  ; 2. the folder OBS Studio installs to by default
  ${If} ${FileExists} "$PROGRAMFILES64\obs-studio\bin\64bit\obs64.exe"
    StrCpy $INSTDIR "$PROGRAMFILES64\obs-studio"
    StrCpy $Found "OBS Studio is in Program Files. Choose another folder only if you use a different OBS Studio."
    Return
  ${EndIf}
  ; 3. not found: the folder page asks
  StrCpy $Found "OBS Studio was not found in the registry or in Program Files. Browse to the folder where it is installed: the one that holds bin\64bit\obs64.exe."
FunctionEnd

Function .onVerifyInstDir
  ${IfNot} ${FileExists} "$INSTDIR\bin\64bit\obs64.exe"
    Abort
  ${EndIf}
FunctionEnd

Section "obsmage" SecMain
  SectionIn RO
  SetRegView 64
  ${IfNot} ${FileExists} "$INSTDIR\bin\64bit\obs64.exe"
    MessageBox MB_ICONSTOP "$INSTDIR is not an OBS Studio folder (no bin\64bit\obs64.exe). Nothing was installed." /SD IDOK
    SetErrorLevel 2
    Abort
  ${EndIf}
  DetailPrint "$Found"
  ; which of OBS Studio's plugin folders this install makes (OBS 33 has none of them; 32 has all), so that the
  ; uninstaller removes only those; a reinstall keeps what the first install recorded
  !insertmacro Made MadeObsPlugins "obs-plugins" $R1
  !insertmacro Made MadeObsPlugins64 "obs-plugins\64bit" $R2
  !insertmacro Made MadeDataObsPlugins "data\obs-plugins" $R3
  SetOverwrite on
  SetOutPath "$INSTDIR\obs-plugins\64bit"
  File "${STAGE}\obs-plugins\64bit\obsmage-core.dll"
  SetOutPath "$INSTDIR\${DATA}\locale"
  File "${STAGE}\${DATA}\locale\en-US.ini"
  SetOutPath "$INSTDIR\${DATA}\tools"
  File "${STAGE}\${DATA}\tools\omg_atoms.py"
  File "${STAGE}\${DATA}\tools\omg_compose.py"
  SetOutPath "$INSTDIR\${DATA}"
  File "${STAGE}\${DATA}\COPYING"
  File "${STAGE}\${DATA}\COPYING.LESSER"
  File "${STAGE}\${DATA}\README-windows.txt"
  WriteUninstaller "$INSTDIR\${DATA}\uninstall-obsmage.exe"
  WriteRegStr HKLM "${UNINST}" "DisplayName" "obsmage (in OBS Studio)"
  WriteRegStr HKLM "${UNINST}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${UNINST}" "Publisher" "INPUTLOOP"
  WriteRegStr HKLM "${UNINST}" "URLInfoAbout" "https://obsmage.com"
  WriteRegStr HKLM "${UNINST}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINST}" "UninstallString" '"$INSTDIR\${DATA}\uninstall-obsmage.exe"'
  WriteRegStr HKLM "${UNINST}" "QuietUninstallString" '"$INSTDIR\${DATA}\uninstall-obsmage.exe" /S'
  WriteRegDWORD HKLM "${UNINST}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINST}" "NoRepair" 1
  WriteRegDWORD HKLM "${UNINST}" "MadeObsPlugins" $R1
  WriteRegDWORD HKLM "${UNINST}" "MadeObsPlugins64" $R2
  WriteRegDWORD HKLM "${UNINST}" "MadeDataObsPlugins" $R3
SectionEnd

Function un.onInit
  SetRegView 64
FunctionEnd

; Removes only what the installer put there, by name; folders only when empty (RMDir without /r). OBS Studio and
; its settings stay.
Section "Uninstall"
  Delete "${UN_OBS}\obs-plugins\64bit\obsmage-core.dll"
  Delete "${UN_OBS}\${DATA}\locale\en-US.ini"
  Delete "${UN_OBS}\${DATA}\tools\omg_atoms.py"
  Delete "${UN_OBS}\${DATA}\tools\omg_compose.py"
  Delete "${UN_OBS}\${DATA}\COPYING"
  Delete "${UN_OBS}\${DATA}\COPYING.LESSER"
  Delete "${UN_OBS}\${DATA}\README-windows.txt"
  ; Python leaves byte code beside the tools when they are run from here
  Delete "${UN_OBS}\${DATA}\tools\__pycache__\omg_atoms.*.pyc"
  Delete "${UN_OBS}\${DATA}\tools\__pycache__\omg_compose.*.pyc"
  Delete "$INSTDIR\uninstall-obsmage.exe"
  RMDir "${UN_OBS}\${DATA}\tools\__pycache__"
  RMDir "${UN_OBS}\${DATA}\tools"
  RMDir "${UN_OBS}\${DATA}\locale"
  RMDir "${UN_OBS}\${DATA}"
  ; OBS Studio's plugin folders: only those the installer made (recorded in the Apps entry), and only when empty
  ReadRegDWORD $0 HKLM "${UNINST}" "MadeDataObsPlugins"
  ${If} $0 == 1
    RMDir "${UN_OBS}\data\obs-plugins"
  ${EndIf}
  ReadRegDWORD $0 HKLM "${UNINST}" "MadeObsPlugins64"
  ${If} $0 == 1
    RMDir "${UN_OBS}\obs-plugins\64bit"
  ${EndIf}
  ReadRegDWORD $0 HKLM "${UNINST}" "MadeObsPlugins"
  ${If} $0 == 1
    RMDir "${UN_OBS}\obs-plugins"
  ${EndIf}
  DeleteRegKey HKLM "${UNINST}"
SectionEnd

; Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
; Mentat (for Corwin, claude-opus-5-5)
