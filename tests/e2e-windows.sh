#!/bin/sh
# e2e-windows.sh -- the Windows build (packaging/windows/omg-win), checked on Linux in POSIX sh. It builds the
# installer from a commit of this repository and judges what came out with objdump, 7z, unzip, cmp, sha256sum,
# grep and awk; tests/windows_pe_check.pl (Perl) is the second witness, reading the DLL itself. What only Windows
# can show (the installer finds OBS Studio or refuses a folder, libobs loads the plugin, the uninstaller cleans
# up) is checked on a Windows runner by .github/workflows/windows.yml.
#   sh tests/e2e-windows.sh               run the checks
#   sh tests/e2e-windows.sh --prove-red   plant a fault in a copy of packaging/; each must turn its check red
# Needs git cmake make zip unzip 7z perl python3 makensis and MinGW-w64 (gcc, dlltool, objdump); without them it
# names what is missing and exits 3, having checked nothing.
# Settings: WIN_SRC, WIN_REF the repository and commit to build (this one, HEAD); PKG=dir checks another copy of
# packaging/ (the plants use this); ONLY="W1 W5" runs only those checks (the build always runs);
# WIN_OBS_CACHE shares the pinned OBS headers between runs.
set -u
here=$(cd "$(dirname "$0")" && pwd); top=$(dirname "$here")

if [ "${1:-}" = --prove-red ]; then
  t=$(mktemp -d); bad=0
  WIN_OBS_CACHE=${WIN_OBS_CACHE:-$t/obs-headers}; export WIN_OBS_CACHE
  plant() {  # name file sed-expr checks
    rm -rf "$t/pkg"; cp -R "$top/packaging" "$t/pkg"
    sed "$3" "$t/pkg/$2" > "$t/x" && cat "$t/x" > "$t/pkg/$2"
    if cmp -s "$top/packaging/$2" "$t/pkg/$2"; then echo "PLANT FAILED  $1"; bad=1; return; fi
    PKG=$t/pkg ONLY=$4 sh "$0" > "$t/log" 2>&1
    if [ $? = 0 ]; then echo "STAYED GREEN  $1"; bad=1; else echo "went red      $1  ($(grep -m1 '^RED' "$t/log" | cut -c1-80))"; fi
  }
  plant "the name takes the clock"                windows/omg-win      's/^name=obsmage-\$version-\$stamp-/name=obsmage-$version-$(date +%s)-/'  W1
  plant "the zip and the installer differ"        windows/omg-win      's#^(cd "\$S" && find#echo >> "$D/README-windows.txt"; &#'             W4
  plant "a .def name OBS does not export"         windows/obs.def      '$s/$/\n  obs_no_such_export/'                                        W10
  plant "secret scan skipped"                     windows/omg-win      's#^OMG_TOOLS=\$TMP/src/tools "\$PY"#true || &#'                      W8
  plant "a staged file left out of the installer" windows/obsmage.nsi  '/^  File "\${STAGE}\\\${DATA}\\locale\\en-US.ini"$/d'                 W5
  plant "a file from outside the stage"           windows/obsmage.nsi  's#^  File "\${STAGE}\\\${DATA}\\COPYING"$#  File "${STAGE}\\..\\src\\COPYING"#' W5
  plant "the uninstaller forgets a file"          windows/obsmage.nsi  '/^  Delete "\${UN_OBS}\\\${DATA}\\COPYING.LESSER"$/d'                 W5
  plant "the uninstaller deletes a whole folder"  windows/obsmage.nsi  's/^  RMDir "\${UN_OBS}\\\${DATA}"$/  RMDir \/r "${UN_OBS}\\${DATA}"/'  W5
  plant "a version written into the script"       windows/obsmage.nsi  's/^VIProductVersion "\${VERSION4}"$/VIProductVersion "9.9.9.9"/'      W6
  plant "a .sha256 that does not check out"       windows/omg-win      's/sumc "\$f")/sumc "$f" | tr 0123456789abcdef 123456789abcdef0)/'   W2
  plant "the DLL takes the clock (sh)"            windows/omg-win      's/-Wl,--no-insert-timestamp //'                                      W3
  plant "the DLL takes the clock (perl)"          windows/omg-win      's/-Wl,--no-insert-timestamp //'                                      W11
  plant "import library names another DLL (sh)"   windows/obs.def      's/^LIBRARY obs\.dll$/LIBRARY libobs.dll/'                            W9
  plant "import library names another DLL (perl)" windows/obs.def      's/^LIBRARY obs\.dll$/LIBRARY libobs.dll/'                            W11
  plant "a version disagreement built anyway"     windows/omg-win      's/^\[ "\$cver" = "\$version" \] || die/[ "$cver" = "$version" ] || true/' W7
  plant "OBS headers at another commit trusted"   windows/omg-win      's/^if \[ "\$have" != "\$OBS_COMMIT" \]; then$/if false; then/'       W12
  rm -rf "$t"
  [ $bad = 0 ] && echo "PROVE-RED OK" || { echo "PROVE-RED FAILED"; exit 1; }
  exit 0
fi

missing=
for c in git cmake make zip unzip 7z perl python3 makensis x86_64-w64-mingw32-objdump x86_64-w64-mingw32-dlltool; do
  command -v "$c" >/dev/null 2>&1 || missing="$missing $c"
done
[ -z "$missing" ] || { echo "e2e-windows: missing:$missing (nothing was checked)"; exit 3; }

SRC=${WIN_SRC:-$top}; REF=${WIN_REF:-HEAD}; PKG=${PKG:-$top/packaging}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT INT TERM
WIN_OBS_CACHE=${WIN_OBS_CACHE:-$T/obs-headers}; export WIN_OBS_CACHE
pass=0; fail=0
ok()  { pass=$((pass + 1)); echo "ok    $1"; }
red() { fail=$((fail + 1)); echo "RED   $1"; }
want() { [ -z "${ONLY:-}" ] && return 0; case " $ONLY " in *" $1 "*) return 0 ;; esac; return 1; }
build() { WIN_SRC=$1 WIN_REF=$2 WIN_OUT=$3 sh "$PKG/windows/omg-win" > "$3.out" 2>&1; }
g() { GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_AUTHOR_NAME=E GIT_AUTHOR_EMAIL=e@example.invalid \
      GIT_COMMITTER_NAME=E GIT_COMMITTER_EMAIL=e@example.invalid git "$@"; }
clone() { g clone -q "$SRC" "$1" && g -C "$1" checkout -q "$rev"; }

rev=$(git -C "$SRC" rev-parse --verify "$REF^{commit}") || { echo "e2e-windows: no commit for $REF"; exit 1; }
ver=$(git -C "$SRC" show "$rev:debian/changelog" | sed -n '1s/^obsmage (\([^)]*\)).*/\1/p')
ct=$(git -C "$SRC" show -s --format=%ct "$rev")
name=obsmage-$ver-$(date -u -d "@$ct" +%Y%m%d-%H%M%S)-$(printf %s "$rev" | cut -c1-12)-windows-x64
pin=$(sed -n 's/^OBS_COMMIT=//p' "$PKG/windows/pins.env")
P=$T/a/public; exe=$P/$name-setup.exe; zip=$P/$name.zip

build "$SRC" "$rev" "$T/a"; rc=$?
mkdir -p "$T/z" "$T/n"
unzip -q "$zip" -d "$T/z" 2>/dev/null; 7z x -y -o"$T/n" "$exe" >/dev/null 2>&1
dll=$T/z/obs-plugins/64bit/obsmage-core.dll

if want W1; then
  [ $rc = 0 ] && [ -s "$exe" ] && [ -s "$zip" ] && [ "$(ls "$P" | wc -l)" = 4 ] \
    && ok "W1 an installer and a zip, named from the commit ($name)" || red "W1 an installer and a zip, named from the commit (rc=$rc; $(tail -n 1 "$T/a.out"))"
fi

if want W2; then
  b=0
  for f in "$exe" "$zip"; do
    [ "$(awk '{ print $2 }' "$f.sha256" 2>/dev/null)" = "$(basename "$f")" ] && (cd "$P" && sha256sum -c --status "$(basename "$f").sha256") || b=1
  done
  [ $b = 0 ] && ok "W2 a .sha256 beside each, naming it and checking out" || red "W2 a .sha256 beside each, naming it and checking out"
fi

if want W3; then
  sleep 1; build "$SRC" "$rev" "$T/b"
  cmp -s "$exe" "$T/b/public/$name-setup.exe" && cmp -s "$zip" "$T/b/public/$name.zip" \
    && ok "W3 a second build elsewhere gives the same bytes" || red "W3 a second build elsewhere gives the same bytes"
fi

if want W4; then
  (cd "$T/z" && find . -type f | LC_ALL=C sort) > "$T/z.list"
  (cd "$T/n" && find . -type f ! -path './$PLUGINSDIR/*' ! -name uninstall-obsmage.exe | LC_ALL=C sort) > "$T/n.list"
  b=0; while read -r f; do cmp -s "$T/z/$f" "$T/n/$f" || b=1; done < "$T/z.list"
  [ -s "$T/z.list" ] && cmp -s "$T/z.list" "$T/n.list" && [ $b = 0 ] && [ -f "$T/n/data/obs-plugins/obsmage-core/uninstall-obsmage.exe" ] \
    && ok "W4 the installer carries the stage byte for byte, plus its uninstaller ($(wc -l < "$T/z.list") files)" \
    || red "W4 the installer carries the stage byte for byte, plus its uninstaller"
fi

if want W5; then
  nsi=$PKG/windows/obsmage.nsi
  data=$(sed -n 's/^!define DATA "\(.*\)"$/\1/p' "$nsi")
  awk -v data="$data" '
    { gsub(/\$[{]DATA[}]/, data) }
    /^[ \t]*SetOutPath "\$INSTDIR/ { s = $0; sub(/^[^"]*"\$INSTDIR\\?/, "", s); sub(/".*$/, "", s); out = s }
    /^[ \t]*File[ \t]/ {
      s = $0; sub(/^[^"]*"/, "", s); sub(/".*$/, "", s)
      if ($0 ~ /\/oname/ || s !~ /^\$[{]STAGE[}]\\/ || s ~ /\\\.\.\\/) { print "OUTSIDE " s; next }
      sub(/^\$[{]STAGE[}]\\/, "", s); n = split(s, p, /\\/); d = (out == "" ? "" : out "\\") p[n]
      print (d == s ? "FILE " s : "MOVED " s " to " d)
    }
    /^[ \t]*Delete "\$[{]UN_OBS[}]\\/ { s = $0; sub(/^[^"]*"\$[{]UN_OBS[}]\\/, "", s); sub(/".*$/, "", s); print "DELETE " s }
  ' "$nsi" | tr '\\' '/' > "$T/nsi.list"
  sed -n 's/^FILE //p' "$T/nsi.list" | LC_ALL=C sort > "$T/f.list"
  sed 's#^\./##' "$T/z.list" > "$T/zs.list"
  b=; grep -q '^\(OUTSIDE\|MOVED\) ' "$T/nsi.list" && b="$b $(grep -m1 '^\(OUTSIDE\|MOVED\) ' "$T/nsi.list");"
  cmp -s "$T/f.list" "$T/zs.list" || b="$b installs other files than were staged;"
  while read -r f; do grep -qx "DELETE $f" "$T/nsi.list" || b="$b the uninstaller leaves $f;"; done < "$T/f.list"
  for f in obs-plugins/64bit/obsmage-core.dll data/obs-plugins/obsmage-core/locale/en-US.ini; do grep -qx "$f" "$T/f.list" || b="$b no $f;"; done
  grep -Eiq '^[[:space:]]*(RMDir[[:space:]]+/r|Delete[[:space:]].*\*\.\*)' "$nsi" && b="$b a recursive or catch-all delete;"
  [ -z "$b" ] && ok "W5 the script installs exactly the stage, from the stage, in OBS's layout, and uninstalls each file by name" \
    || red "W5 the script installs exactly the stage, from the stage, in OBS's layout, and uninstalls each file by name:$b"
fi

if want W6; then
  b=
  grep -v '^[[:space:]]*;' "$PKG/windows/obsmage.nsi" | grep -Eq '[0-9]+\.[0-9]+\.[0-9]+' && b="$b the script has a version literal;"
  grep -q "^obsmage $ver for Windows" "$T/z/data/obs-plugins/obsmage-core/README-windows.txt" 2>/dev/null && grep -q "at commit $rev$" "$T/z/data/obs-plugins/obsmage-core/README-windows.txt" || b="$b README-windows.txt;"
  strings -a "$dll" 2>/dev/null | grep -qx "$ver" || b="$b the DLL;"
  strings -el "$exe" 2>/dev/null | grep -qx "$ver" || b="$b the installer's file properties;"
  [ -z "$b" ] && ok "W6 the version is debian/changelog's ($ver) in the README, the DLL and the installer, and nowhere written by hand" \
    || red "W6 the version comes from one place:$b"
fi

if want W7; then
  clone "$T/c7" && sed -i "s/^project(obsmage-core VERSION [^ ]*/project(obsmage-core VERSION 9.9.9/" "$T/c7/plugin/obsmage-core/CMakeLists.txt" \
    && g -C "$T/c7" commit -q -am "disagree" && build "$T/c7" HEAD "$T/o7"; rc=$?
  [ $rc = 1 ] && grep -q 'version disagrees' "$T/o7.out" && [ -z "$(ls "$T/o7/public" 2>/dev/null)" ] \
    && ok "W7 a CMakeLists version other than debian/changelog's is refused, nothing staged" || red "W7 a version disagreement is refused (rc=$rc)"
fi

if want W8; then
  tok=gh; tok="${tok}p_$(printf '%s' 0123456789abcdefghijklmnopqrstuvwxyzAB)"
  clone "$T/c8" && printf 'Token=%s\n' "$tok" >> "$T/c8/plugin/obsmage-core/data/locale/en-US.ini" \
    && g -C "$T/c8" commit -q -am "leak" && build "$T/c8" HEAD "$T/o8"; rc=$?
  [ $rc = 1 ] && grep -q 'secret-scan refused' "$T/o8.out" && [ -z "$(ls "$T/o8/public" 2>/dev/null)" ] && ! grep -rq "$tok" "$T/o8.out" "$T/o8/work/win.log" \
    && ok "W8 a credential in a shipped file refuses the build, nothing staged, the value never printed" || red "W8 a credential in a shipped file refuses the build (rc=$rc)"
fi

if want W9; then
  got=$(x86_64-w64-mingw32-objdump -p "$dll" 2>/dev/null | sed -n 's/^[[:space:]]*DLL Name: //p' | LC_ALL=C sort | tr '\n' ' ')
  [ "$got" = "KERNEL32.dll msvcrt.dll obs-frontend-api.dll obs.dll " ] \
    && ok "W9 the DLL imports from OBS's obs.dll and obs-frontend-api.dll and Windows' own, nothing else" || red "W9 the DLL's imports ($got)"
fi

if want W10; then
  b=
  for d in obs:libobs obs-frontend-api:frontend/api; do
    for f in $(sed -e '1,/^EXPORTS$/d' -n -e 's/^[[:space:]]*\([A-Za-z_][A-Za-z0-9_]*\).*/\1/p' "$PKG/windows/${d%%:*}.def"); do
      grep -rqE "^EXPORT[^;(]*[^A-Za-z0-9_]$f[[:space:]]*\(" "$WIN_OBS_CACHE/$pin/${d#*:}" || b="$b $f"
    done
  done
  [ -z "$b" ] && ok "W10 every name in the .def files is an EXPORT in OBS's headers at the pin" || red "W10 not exported by OBS at the pin:$b"
fi

if want W11; then
  perl "$here/windows_pe_check.pl" "$dll" "$PKG/windows/obs.def" "$PKG/windows/obs-frontend-api.def" > "$T/pe.out" 2>&1 \
    && ok "W11 the Perl witness agrees ($(tail -n 1 "$T/pe.out"))" || red "W11 the Perl witness: $(grep -m1 '^RED' "$T/pe.out" || tail -n 1 "$T/pe.out")"
fi

if want W12; then
  C=$T/badcache; mkdir -p "$C/$pin" && g -C "$C/$pin" init -q && echo x > "$C/$pin/x" && g -C "$C/$pin" add x && g -C "$C/$pin" commit -q -m other
  WIN_OBS_CACHE=$C build "$SRC" "$rev" "$T/o12"; rc=$?
  [ $rc = 0 ] && grep -q 'fetching again' "$T/o12/work/win.log" && [ "$(git -C "$C/$pin" rev-parse HEAD 2>/dev/null)" = "$pin" ] \
    && ok "W12 OBS headers at another commit than the pin are fetched again, at the pin" || red "W12 OBS headers at another commit than the pin (rc=$rc)"
fi

echo "e2e-windows: $pass ok, $fail RED"
[ $fail = 0 ]

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
