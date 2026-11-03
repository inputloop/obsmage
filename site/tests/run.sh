#!/bin/sh
# run.sh -- every check of obsmage.com, in order: build, the static checks (Python), the same with
# releases closed, the browser's atom layer and composer against the Python tools (node), the deploy
# scripts against a fake nginx (sh), and the site in Chromium (node + playwright, when installed).
#   sh site/tests/run.sh                ends ALL CHECKS PASSED
#   sh site/tests/run.sh --prove-red    plants one fault per promise in a copy; each must turn a check red; ends PROVE-RED OK
# TOPOLOGY_DIR (default ../topology beside the repository) is staged as the front page's drawing app.
# SHOTS=dir keeps the browser's screenshots. SKIP_BROWSER=1 leaves the browser out.
set -u
site=$(cd "$(dirname "$0")/.." && pwd); top=$(dirname "$site")
export TOPOLOGY_DIR=${TOPOLOGY_DIR:-$top/../topology}
node=${NODE:-node}
have_browser() { [ "${SKIP_BROWSER:-}" != 1 ] && "$node" -e "require('playwright')" >/dev/null 2>&1; }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT INT TERM

if [ "${1:-}" != --prove-red ]; then
  bad=0
  step() { printf '\n== %s\n' "$1"; }
  run() { if "$@"; then :; else echo "RED: $*"; bad=1; fi; }
  step "build"; run python3 "$site/build.py"
  step "static checks (python)"; run python3 "$site/tests/check_site.py"
  step "static checks with releases closed (the other position of site.conf's one line)"
  sed 's/^releases: .*/releases: closed/' "$site/site.conf" > "$T/closed.conf"
  run python3 "$site/build.py" --conf "$T/closed.conf" --out "$T/closed" --generated "$T/closed-gen" >/dev/null
  run python3 "$site/tests/check_site.py" "$T/closed" "$T/closed-gen" "$T/closed.conf"
  step "the atom layer in JS against omg_atoms.py (node)"; run "$node" "$site/tests/atoms-vectors.mjs"
  step "the composer's audit in JS against omg_compose.py (node)"; run "$node" "$site/tests/compose-vectors.mjs"
  step "install, rollback and the reload wait, against a fake nginx (sh)"; run sh "$site/tests/test-install.sh"
  if have_browser; then step "the site in Chromium: 390/1280/1920, light and dark, the demo worked (playwright)"; run "$node" "$site/tests/browser.cjs"
  else step "browser checks skipped (SKIP_BROWSER=1, or playwright is not installed)"; fi
  [ $bad = 0 ] && { echo; echo "ALL CHECKS PASSED"; exit 0; }
  echo; echo "SOME CHECKS FAILED"; exit 1
fi

# ---- prove-red: each plant must turn a check red --------------------------------------------------
bad=0
python3 "$site/build.py" > /dev/null || { echo "build failed; cannot plant"; exit 1; }
red() { if "$@" > "$T/log" 2>&1; then echo "STAYED GREEN  $label"; bad=1; else echo "went red      $label  ($(grep -m1 -E '^(FAIL|RED)' "$T/log" | cut -c1-80))"; fi; }
pub() { rm -rf "$T/pub"; cp -R "$site/public" "$T/pub"; }
sedi() { f=$1; shift; sed "$@" "$f" > "$T/sed.tmp" && if cmp -s "$f" "$T/sed.tmp"; then echo "PLANT FAILED  $label"; bad=1; else cp "$T/sed.tmp" "$f"; fi; }
static() { red python3 "$site/tests/check_site.py" "$T/pub" "$site/generated" "$site/site.conf"; }

label="an inline script";                pub; sedi "$T/pub/index.html" 's#</main>#<script>void 0</script></main>#'; static
label="an inline style";                 pub; sedi "$T/pub/colophon.html" 's#<h1>#<h1 style="color:red">#'; static
label="a private repository's address";  pub; sedi "$T/pub/index.html" 's#</main>#<a href="https://github.com/inputloop/c4">c4</a></main>#'; static
label="a script without its label";      pub; sedi "$T/pub/js/front.js" '1d'; static
label="a script without its licence row"; pub; sedi "$T/pub/jslicense.html" 's#href="js/demo.js"#href="js/demo.jsx"#g'; static
label="a broken internal link";          pub; sedi "$T/pub/index.html" 's#href="demo.html"#href="demo2.html"#'; static
label="a script that phones home";       pub; sedi "$T/pub/js/front.js" 's#if (!f) return;#if (!f) return; fetch("/x");#'; static
label="the demo's sample not the sample"; pub; sedi "$T/pub/demo.html" 's#Sample Studio#Sample Stuido#'; static
label="the drawing loses a part";        pub; sedi "$T/pub/drawings/obsmage.json" 's#"id": "healer"#"id": "heal3r"#'; static
label="releases open but not mapped";    rm -rf "$T/gen"; cp -R "$site/generated" "$T/gen"; echo "# nothing" > "$T/gen/releases.conf"; pub
                                         red python3 "$site/tests/check_site.py" "$T/pub" "$T/gen" "$site/site.conf"
label="the site policy allows a connection"; rm -rf "$T/dep"; cp -R "$site/deploy" "$T/dep"; sedi "$T/dep/nginx-obsmage.com.conf" "s#connect-src 'none'#connect-src 'self' https:#"; pub
                                         DEPLOY_DIR=$T/dep red python3 "$site/tests/check_site.py" "$T/pub" "$site/generated" "$site/site.conf"
label="the atom layer spells a float the JS way"; OMG_PROVE_RED=1 red "$node" "$site/tests/atoms-vectors.mjs"
label="the composer counts unbound as by index";  OMG_PROVE_RED=1 red "$node" "$site/tests/compose-vectors.mjs"
echo "-- the deploy scripts' own plants:"
sh "$site/tests/test-install.sh" --prove-red || bad=1
if have_browser; then
  br() { SITE_OUT=$T/pub QUICK=1 red "$node" "$site/tests/browser.cjs"; }
  label="(browser) the BOM is lost on the way back"; pub; sedi "$T/pub/js/omg-atoms.js" "s#return (meta.bom ? '\\\\ufeff' : '') + text;#return text;#"; br
  label="(browser) a picture from another host";     pub; sedi "$T/pub/index.html" 's#</main>#<img src="https://example.org/x.png" alt=""></main>#'; br
  label="(browser) the page scrolls sideways";       pub; sedi "$T/pub/css/site.css" 's#^\.lede { #.lede { min-width: 640px; #'; br
  label="(browser) a grey too light to read";        pub; sedi "$T/pub/css/site.css" 's#--text-dim: \#595959;#--text-dim: \#b0b0b0;#'; br
  label="(browser) withheld values shown";           pub; sedi "$T/pub/js/demo.js" "s#var hide = \$('reveal').checked ? \[\] : masks(S.file)#var hide = []#"; br
  label="(browser) a drag writes nothing";           pub; sedi "$T/pub/js/demo.js" 's#if (s.x !== it.x || s.y !== it.y) setPos(it.item, s.x, s.y);#void s;#'; br
else echo "browser plants skipped (SKIP_BROWSER=1, or playwright is not installed)"; fi
[ $bad = 0 ] && { echo "PROVE-RED OK"; exit 0; }
echo "PROVE-RED FAILED"; exit 1

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
