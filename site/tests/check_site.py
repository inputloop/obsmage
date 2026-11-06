#!/usr/bin/env python3
"""check_site.py: static checks of a built obsmage.com (site/public) and its deploy files.

    python3 site/tests/check_site.py [PUBLIC_DIR] [GENERATED_DIR] [SITE_CONF]

Each check is one promise the site makes; tests/run.sh --prove-red plants a fault for each.
Standard library only. Exit 0 when every check passes.
"""
import html.parser
import json
import os
import re
import sys

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = os.path.dirname(SITE)
PUB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SITE, "public")
GEN = sys.argv[2] if len(sys.argv) > 2 else os.path.join(SITE, "generated")
CONF = sys.argv[3] if len(sys.argv) > 3 else os.path.join(SITE, "site.conf")
DEPLOY = os.environ.get("DEPLOY_DIR", os.path.join(SITE, "deploy"))
sys.path.insert(0, os.path.join(TOP, "tools"))
import omg_atoms as A  # noqa: E402

# every address another host may be given, each checked public (2026-11-02)
ALLOWED = {
    "https://github.com/inputloop/obsmage", "https://github.com/inputloop/obsmage-corwin",
    "https://github.com/inputloop/corwin.cloud", "https://github.com/inputloop/topology/tree/corwin",
    "https://github.com/inputloop/about-corwin", "https://corwin.cloud/", "https://obsproject.com/",
    "https://www.gnu.org/licenses/gpl-3.0.html",
    # the "Drawn by" credits (2026-11-05): the shop's own pages for INPUTLOOP, Bryant and Corwin
    "https://github.com/inputloop", "https://github.com/takushieternal", "https://aboutcorwin.com/", "mailto:corwin@bru.st",
}
PRIVATE = ["c4"]
PAGES = ["index.html", "demo.html", "colophon.html", "jslicense.html", "404.html", "LICENSES/index.html"]
fails, passed = [], [0]


def check(cond, desc):
    if cond:
        passed[0] += 1
    else:
        fails.append(desc)
        print("FAIL " + desc)


class Page(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.scripts, self.inline, self.styles, self.ids, self.tags = [], [], [], 0, set(), []
        self._in_script = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a))
        if "id" in a:
            self.ids.add(a["id"])
        if "style" in a or tag == "style":
            self.styles += 1
        for k in ("href", "src", "action", "formaction", "poster", "data"):
            if a.get(k) is not None and not (tag == "iframe" and k == "src" and False):
                self.links.append((tag, k, a[k]))
        if tag == "script":
            if a.get("src"):
                self.scripts.append(a["src"])
            else:
                self._in_script = a.get("type", "")

    def handle_data(self, d):
        if self._in_script is not None and d.strip():
            self.inline.append(self._in_script)

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = None


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def parse(rel):
    p = Page()
    p.feed(read(os.path.join(PUB, rel)))
    return p


conf = {}
for ln in read(CONF).split("\n"):
    ln = ln.split("#", 1)[0].strip()
    if ":" in ln:
        k, v = ln.split(":", 1)
        conf[k.strip()] = v.strip()
OPEN = conf.get("releases") == "open"

# 1. every page exists; internal links resolve; external links are on the list
for rel in PAGES:
    check(os.path.isfile(os.path.join(PUB, rel)), "page %s exists" % rel)
pages = {rel: parse(rel) for rel in PAGES if os.path.isfile(os.path.join(PUB, rel))}
for rel, p in pages.items():
    base = os.path.dirname(rel)
    for tag, k, u in p.links:
        if re.match(r"^[a-z][a-z0-9+.-]*:", u, re.I):
            check(u in ALLOWED, "%s: %s=%s is not an allowed public address" % (rel, k, u))
            continue
        if u.startswith("#"):
            check(u[1:] in p.ids, "%s: #%s has no target" % (rel, u[1:]))
            continue
        path = u.split("#")[0].split("?")[0]
        if path.startswith("dist/") or path.startswith("../dist/"):
            continue   # served from the staged bundles, checked by the release checks below
        target = os.path.normpath(os.path.join(PUB, base, path)) if not path.startswith("/") else os.path.join(PUB, path.lstrip("/"))
        if path.endswith("/") or path == "" or path == "./" or path == "../":
            target = os.path.join(target, "index.html")
        check(os.path.exists(target), "%s: link %s resolves (%s)" % (rel, u, os.path.relpath(target, PUB)))

# 2. no inline script (a JSON data block is not a script), no inline style, nothing from another host
for rel, p in pages.items():
    check(all(t == "application/json" for t in p.inline), "%s: no inline script (found types %s)" % (rel, p.inline))
    check(p.styles == 0, "%s: no style attribute or <style> element" % rel)
    for tag, a in p.tags:
        if tag in ("script", "img", "iframe", "link", "source", "video", "audio") and re.match(r"^(https?:)?//", a.get("src") or (a.get("href") if tag == "link" else "") or ""):
            check(False, "%s: <%s> loads from another host" % (rel, tag))
for dp, _, fs in os.walk(os.path.join(PUB, "css")):
    for f in fs:
        t = read(os.path.join(dp, f))
        check(not re.search(r"url\(\s*['\"]?(https?:)?//", t) and "@import" not in t, "css/%s loads nothing from another host" % f)

# 3. every script of ours carries a LibreJS label and has its row in jslicense.html
jsl = read(os.path.join(PUB, "jslicense.html"))
for f in sorted(os.listdir(os.path.join(PUB, "js"))):
    t = read(os.path.join(PUB, "js", f))
    check(t.startswith("// @license magnet:") and t.rstrip().endswith("// @license-end"), "js/%s has its LibreJS label" % f)
    check('href="js/%s"' % f in jsl, "js/%s has a row in jslicense.html" % f)
    check(not re.search(r"\b(fetch|XMLHttpRequest|WebSocket|sendBeacon|EventSource|importScripts)\s*\(", t), "js/%s makes no network request" % f)

# 4. no private repository is given an address; the private recipe never feeds the site
alltext = "".join(read(os.path.join(dp, f)) for dp, _, fs in os.walk(PUB) for f in fs
                  if f.endswith((".html", ".js", ".json", ".css")) and "/topology" not in dp.replace(os.sep, "/"))
for n in PRIVATE:
    check(not re.search(r"github\.com/[\w.-]+/%s\b" % re.escape(n), alltext), "no address for the private repository %s" % n)
check("GSUS" not in alltext and "Avalon" not in alltext and "avalon" not in alltext, "nothing from Corwin's own setup (names from obsmage-corwin) is in the site")

# 5. the sample is invented: every credential in it is FAKE, every host example.invalid
cfg = os.path.join(SITE, "sample", "config")
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as t:
    A.split(cfg, os.path.join(t, "a"), os.path.join(t, "v.kv"))
    vault = A.load_vault(os.path.join(t, "v.kv"))
check(len(vault) >= 4, "the sample has credentials to withhold (%d)" % len(vault))
for k, v in vault.items():
    check(v.strip('"').startswith("FAKE"), "sample credential %s is visibly made up" % k.split("|")[-1])
hosts = re.findall(r"[a-z]+://([\w.-]+)", "".join(read(os.path.join(dp, f)) for dp, _, fs in os.walk(cfg) for f in fs))
check(all(h.endswith("example.invalid") for h in hosts), "the sample names no real host (%s)" % sorted(set(hosts)))
demo = read(os.path.join(PUB, "demo.html"))
m = re.search(r'<script id="sample" type="application/json">(.*?)</script>', demo, re.S)
check(m is not None, "demo.html carries the sample as a data block")
if m:
    data = json.loads(m.group(1))
    check(sorted(data["files"]) == sorted(A.config_files(cfg)), "the demo's sample is site/sample/config, every file")
    check(all(data["files"][r] == open(os.path.join(cfg, r), encoding="utf-8", newline="").read() for r in data["files"]),
          "the demo's sample is site/sample/config byte for byte")

# 6. the deploy policies stay strict
for name in ("nginx-obsmage.com.conf", "obsmage.com.interim.conf"):
    t = read(os.path.join(DEPLOY, name))
    pols = re.findall(r'Content-Security-Policy "([^"]*)"', t)
    check(pols, "%s sets a policy" % name)
    for pol in pols:
        check("unsafe-inline" not in pol and "unsafe-eval" not in pol, "%s: no unsafe-inline or unsafe-eval in the site policy" % name)
        check("connect-src 'none'" in pol, "%s: the site's pages may connect nowhere" % name)
        check(not re.search(r"https?:|\*", pol), "%s: no other host in the site policy" % name)
    check("include snippets/obsmage-releases.conf;" in t and "include snippets/obsmage-topology-csp.conf;" in t, "%s includes both generated snippets" % name)
    check(not re.search(r"location\s+~", t), "%s has no regex location (it would override /topology/'s policy)" % name)
tls = read(os.path.join(DEPLOY, "nginx-obsmage.com.conf"))
check(re.search(r"listen 80;.*?return 301 https://obsmage\.com\$request_uri;", tls, re.S) is not None, "http answers 301 to https")
check("server_name www.obsmage.com;" in tls and "/etc/letsencrypt/live/obsmage.com/fullchain.pem" in tls, "www has the certificate and its own redirect")
tp = read(os.path.join(GEN, "topology-csp.conf"))
if "no topology staged" not in tp:
    pol = re.search(r'"([^"]*)"', tp).group(1)
    check("connect-src 'self'" in pol and not re.search(r"https?:", pol), "topology may fetch from this origin only")
    check("'unsafe-eval'" not in pol, "topology's policy allows no eval")

# 6b. every page credits "Drawn by" INPUTLOOP, Bryant and Corwin, each a link, and names a human to write to
for rel in PAGES:
    if rel not in pages:
        continue
    t = read(os.path.join(PUB, rel))
    m = re.search(r'Drawn by</span><span class="tb-v">(.*?)</span>', t, re.S)
    cell = m.group(1) if m else ""
    for name, url in (("INPUTLOOP", "https://github.com/inputloop"), ("Bryant", "https://github.com/takushieternal"), ("Corwin", "https://aboutcorwin.com/")):
        check('<a href="%s">%s</a>' % (url, name) in cell, "%s: Drawn by links %s" % (rel, name))
    check("Corwin Brust" in t and 'href="mailto:corwin@bru.st"' in t, "%s: a human is named, with a way to write" % rel)

# 7. releases follow site.conf, one line
rel = read(os.path.join(GEN, "releases.conf"))
index = read(os.path.join(PUB, "index.html"))
if OPEN:
    check("alias /var/lib/obsmage-dist/public/;" in rel and "location ^~ /dist/" in rel, "releases open: nginx maps /dist/ to the staged bundles")
    check('href="dist/channel.json"' in index, "releases open: the page links the channel feed")
    check('href="dist/windows/"' in index and "Windows" in index, "releases open: the page names the Windows folder and says what is in it")
else:
    check("location" not in rel, "releases closed: nothing is mapped at /dist/")
    check("dist/" not in index and "Releases open when the project does" in index, "releases closed: the page links no bundle and says why")

# 8. the drawing is topology forge's own format, and shows the five parts in order
d = json.load(open(os.path.join(PUB, "drawings", "obsmage.json"), encoding="utf-8"))
check(d.get("format") == "topoforge" and d.get("version") == 1 and len(d["pages"]) == 1, "the drawing is topoforge JSON, one page")
ids = {n["id"] for n in d["pages"][0]["nodes"]}
check({"obs", "atoms", "composer", "healer", "releases"} <= ids, "the drawing has OBS, atoms, composer, healer and releases")
chain = [(l["a"]["id"], l["b"]["id"]) for l in d["pages"][0]["links"]]
check(all(p in chain for p in [("obs", "atoms"), ("atoms", "composer"), ("composer", "healer"), ("healer", "releases")]), "the drawing links them in order")
check(all(l["a"]["id"] in ids and l["b"]["id"] in ids for l in d["pages"][0]["links"]), "every link in the drawing joins two shapes")

# 9. accessibility basics the browser suite does not measure
for rel, p in pages.items():
    t = read(os.path.join(PUB, rel))
    check('<html lang="en">' in t and '<meta name="viewport"' in t and t.count("<h1") == 1, "%s: lang, viewport, one h1" % rel)
    check('class="skip" href="#main"' in t and 'id="main"' in t, "%s: a skip link to its main" % rel)
    for tag, a in p.tags:
        if tag == "img":
            check("alt" in a, "%s: every img has alt" % rel)
        if tag in ("input", "select", "textarea") and a.get("type") != "hidden":
            check(a.get("id") and (('for="%s"' % a["id"]) in t or a.get("aria-label") or a.get("aria-labelledby") or re.search(r"<label[^>]*>[^<]*<%s[^>]*id=\"%s\"" % (tag, a["id"]), t)),
                  "%s: <%s id=%s> has a label" % (rel, tag, a.get("id")))
        if tag == "iframe":
            check(bool(a.get("title")), "%s: the iframe has a title" % rel)

print("check_site: %d passed, %d failed" % (passed[0], len(fails)))
sys.exit(1 if fails else 0)

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
