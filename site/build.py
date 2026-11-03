#!/usr/bin/env python3
"""build.py: obsmage.com, built the way corwin.cloud is built (plain files, no framework).

    TOPOLOGY_DIR=../topology python3 site/build.py [--out DIR]

Writes site/public/ (what nginx serves) and site/generated/ (the policy for /topology/, and the
releases snippet nginx includes). Reads:
  site/site.conf         one setting per line; `releases: closed` until Corwin or Bryant opens
                         the project ("obsmage is public; publish its releases"), then `open`
  site/sample/           the invented OBS setup the demo starts from (make-sample.py made it)
  tools/omg_atoms.py     to count the sample's atoms for the words on the page (the demo itself
                         runs site/src/js/omg-atoms.js, which the tests hold to the same output)
  TOPOLOGY_DIR           a checkout of topology (branch corwin); its own bin/stage-www.sh stages
                         the drawing app into public/topology/, as corwin.cloud's build does.
                         Without one, the front door says so and shows the picture as a figure.
Python 3.8 or later, standard library only. Nothing is fetched from anywhere.
"""
import argparse
import base64
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

SITE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(SITE)
sys.path.insert(0, os.path.join(TOP, "tools"))
import omg_atoms as A  # noqa: E402

e = html.escape
GEN = os.path.join(SITE, "generated")
DOC_NAME = "obsmage, drawn"
# Public addresses only, each checked public before it went in (2026-11-02: obsmage and
# obsmage-corwin made public by Corwin at 17:44 CT; no code.bru.st copy of either exists yet).
PUBLIC = {
    "obsmage": "https://github.com/inputloop/obsmage",
    "obsmage-corwin": "https://github.com/inputloop/obsmage-corwin",
    "corwin.cloud": "https://github.com/inputloop/corwin.cloud",
    "topology": "https://github.com/inputloop/topology/tree/corwin",
    "about-corwin": "https://github.com/inputloop/about-corwin",
    "corwin.cloud site": "https://corwin.cloud/",
    "obs": "https://obsproject.com/",
}
PRIVATE_NAMES = ["c4"]   # still private: named, never linked (check_site.py fails on an address for one)


def read_conf(path=None):
    conf = {"releases": "closed"}
    with open(path or os.path.join(SITE, "site.conf"), encoding="utf-8") as f:
        for ln in f:
            ln = ln.split("#", 1)[0].strip()
            if ":" in ln:
                k, v = ln.split(":", 1)
                conf[k.strip()] = v.strip()
    if conf["releases"] not in ("closed", "open"):
        raise SystemExit("site.conf: releases must be closed or open, not %r" % conf["releases"])
    return conf


def revision():
    try:
        r = subprocess.run(["git", "describe", "--always", "--dirty"], cwd=TOP, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, universal_newlines=True, timeout=10)
        rev = r.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        rev = "unknown"
    return rev, time.strftime("%Y-%m-%d", time.gmtime(int(os.environ.get("SOURCE_DATE_EPOCH", time.time()))))


def sample_facts():
    """Count the sample with omg_atoms.py itself, so the page's numbers are derived, not typed."""
    cfg = os.path.join(SITE, "sample", "config")
    with tempfile.TemporaryDirectory() as t:
        counts = A.split(cfg, os.path.join(t, "atoms"), os.path.join(t, "vault.kv"))
        bad, missing, leaks = A.verify(cfg)
        video = open(os.path.join(t, "atoms", "basic", "profiles", "Sample_Studio", "basic.ini", "set-Video.kv"), encoding="utf-8").read()
        twitch = open(os.path.join(t, "atoms", "basic", "profiles", "Sample_Studio", "basic.ini", "set-Twitch.kv"), encoding="utf-8").read()
    files = sorted(A.config_files(cfg))
    return {"counts": counts, "atoms": sum(counts.values()), "files": files, "lossless": not (bad or missing or leaks),
            "video": video.strip().split("\n")[:2], "twitch": twitch.strip().split("\n")}


# ---- the drawing (topology forge's own JSON, opened with its ?load=) ------------------------------

LAYERS = [("words", "Words"), ("flow", "Flow: how it works"), ("parts", "Parts"), ("held", "Kept on your machine")]


def drawing(conf):
    nodes, links = [], []

    def node(nid, typ, x, y, w, h, text, layer, what):
        nodes.append({"id": nid, "type": typ, "x": x, "y": y, "w": w, "h": h, "text": text, "layer": layer,
                      "parent": None, "props": {}, "data": {"what": what}, "style": {}})

    def link(i, a, b, text, dash=False, layer="flow"):
        links.append({"id": "l%d" % i, "a": {"id": a, "port": None}, "b": {"id": b, "port": None}, "route": "orthogonal",
                      "text": text, "layer": layer, "arrows": "end", "props": {},
                      "style": {"dash": "6 4"} if dash else {}, "data": {}})

    node("title", "text", 0, -170, 1180, 70,
         "obsmage: OBS Studio kept as plain words.\nEvery setting a key and a value; split, read, changed, joined back exactly.",
         "words", "What this drawing is.")
    node("obs", "desktop", 0, 0, 150, 120, "OBS Studio\n(your profiles and scenes)", "parts",
         "OBS writes INI and JSON files. obsmage reads them where OBS keeps them, and writes only when asked, after a dated backup.")
    node("atoms", "database", 300, 0, 170, 120, "Atoms\none key, one value", "parts",
         "omg_atoms.py splits every file into sets of key=value lines and joins them back: INI byte for byte, JSON as OBS reads it.")
    node("vault", "storage", 300, 220, 170, 100, "Vault\n(credentials, this machine)", "held",
         "Stream keys, tokens and passwords become @secret(len=N) in the atoms. The value stays in a vault, mode 600, never published.")
    node("composer", "rect", 600, 0, 170, 120, "Composer\nscreen maps", "parts",
         "omg_compose.py checks which screen captures bind by index (they drift) and which by stable id, and keeps screen-map scenes in step. It hides, never deletes.")
    node("healer", "server", 900, 0, 170, 120, "Healer\nfollows main, builds", "parts",
         "omg-heal, on a timer: fetches main, builds the Debian package and the plugin, records each run. Nothing is installed by it.")
    rel = "Releases\n(open when the project does)" if conf["releases"] == "closed" else "Releases\nsha256 and a channel feed"
    node("releases", "document", 1200, 0, 170, 120, rel, "parts",
         "Versioned tarballs and a Debian package, each with its sha256, named in one channel feed. Built and kept now; published when the project opens.")
    node("you", "user", 600, 220, 110, 110, "You\n(this browser)", "held",
         "The demo on this site runs here, on an invented setup or your own files. Nothing is sent anywhere.")
    link(1, "obs", "atoms", "split")
    link(2, "atoms", "obs", "join, exactly", dash=True)
    link(3, "atoms", "vault", "withheld")
    link(4, "atoms", "composer", "reads only its atoms")
    link(5, "composer", "healer", "tested, built")
    link(6, "healer", "releases", "sha256 + feed")
    link(7, "you", "atoms", "try it", dash=True, layer="held")
    page = {"id": "page-obsmage", "name": "obsmage", "activeLayer": "flow",
            "layers": [{"id": k, "name": v, "visible": True, "locked": False} for k, v in LAYERS],
            "nodes": nodes, "links": links}
    return {"format": "topoforge", "version": 1, "name": DOC_NAME, "cur": 0, "pages": [page],
            "settings": {"grid": 20, "snap": True, "showGrid": False, "guides": True, "netLabels": True,
                         "ifLabels": True, "minimap": False, "defaultRoute": "orthogonal"}}


def flow_svg(conf):
    """The same picture as a plain figure: for phones, for scripts off, for no topology checkout."""
    steps = [("OBS Studio", "your files"), ("Atoms", "key = value"), ("Composer", "screen maps"),
             ("Healer", "follows main"), ("Releases", "when it opens" if conf["releases"] == "closed" else "sha256 + feed")]
    w, h, bw, gap = 1000, 150, 160, 50
    out = ['<svg class="flow" viewBox="0 0 %d %d" role="img" aria-labelledby="flow-t flow-d" xmlns="http://www.w3.org/2000/svg">' % (w, h),
           '<title id="flow-t">How obsmage works</title>',
           '<desc id="flow-d">%s</desc>' % e(", then ".join("%s (%s)" % s for s in steps)),
           '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
           '<path d="M0,0 L10,5 L0,10 z" class="flow-head"/></marker></defs>']
    for i, (a, b) in enumerate(steps):
        x = 10 + i * (bw + gap)
        out.append('<g class="flow-step"><rect x="%d" y="30" width="%d" height="80" class="flow-box"/>'
                   '<text x="%d" y="64" class="flow-a">%s</text><text x="%d" y="90" class="flow-b">%s</text></g>'
                   % (x, bw, x + bw / 2, e(a), x + bw / 2, e(b)))
        if i:
            out.append('<line x1="%d" y1="70" x2="%d" y2="70" class="flow-line" marker-end="url(#arr)"/>' % (x - gap + 4, x - 6))
    out.append('</svg>')
    return "".join(out)


# ---- pages ------------------------------------------------------------------------------------------

def head(title, desc, here, extra=""):
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<title>%s</title>\n<meta name="description" content="%s">\n'
            '<meta name="color-scheme" content="light dark">\n'
            '<link rel="icon" href="favicon.svg" type="image/svg+xml">\n'
            '<link rel="stylesheet" href="css/site.css">\n'
            '<script src="js/look.js"></script>\n%s</head>\n<body class="page-%s">\n'
            '<a class="skip" href="#main">Skip to the content</a>\n'
            '<header class="bar"><a class="mark" href="./" aria-label="obsmage, home">obsmage</a>'
            '<nav aria-label="Site"><ul>%s</ul></nav></header>\n'
            % (e(title), e(desc, quote=True), extra, here, nav(here)))


def nav(here):
    items = [("index", "./", "The picture"), ("demo", "demo.html", "Try it"), ("index-rel", "./#releases", "Releases"),
             ("colophon", "colophon.html", "Colophon")]
    return "".join('<li><a href="%s"%s>%s</a></li>' % (h, ' aria-current="page"' if k == here else "", t) for k, h, t in items)


def foot(rev, day):
    cells = [("Project", "obsmage"), ("Sheet", "obsmage.com"), ("Drawn by", "its own toolchain"),
             ("Revision", rev), ("Built", day)]
    block = "".join('<div class="tb-cell"><span class="tb-k">%s</span><span class="tb-v">%s</span></div>' % (e(k), e(v)) for k, v in cells)
    return ('<footer class="foot"><div class="titleblock" aria-label="About this page">%s</div>'
            '<p class="foot-line">Free software. Copyright 2026 INPUTLOOP; code GPL-3.0-or-later OR LGPL-3.0-or-later, words CC-BY-SA-4.0. '
            '<a href="colophon.html">Colophon and credits</a> · <a href="jslicense.html" data-jslicense="1">JavaScript licences</a> · '
            '<span class="theme-pick js-only">Theme: <button type="button" data-theme-set="auto">auto</button> '
            '<button type="button" data-theme-set="light">light</button> <button type="button" data-theme-set="dark">dark</button></span></p>'
            '</footer>\n</body>\n</html>\n' % block)


def releases_section(conf):
    if conf["releases"] == "open":
        body = ('<p>Each release is a versioned source tarball and a Debian package for Ubuntu 26.04 (amd64), each with its '
                'sha256. <a href="dist/channel.json">The channel feed</a> names the newest; '
                '<a href="dist/SHA256SUMS">SHA256SUMS</a> lists every file; <a href="dist/">all releases</a>. '
                'Every bundle is checked for credentials before it is served.</p>'
                '<p class="hint">Check before you install: <code>sha256sum -c SHA256SUMS</code>. The packages are not signed yet; '
                'a signature will sit beside each one when they are. The source: <a href="%s">inputloop/obsmage</a>.</p>' % PUBLIC["obsmage"])
    else:
        body = ('<p><strong>Releases open when the project does.</strong> The pipeline already runs: every build makes a '
                'versioned source tarball and a Debian package, each with its sha256, named in one channel feed. '
                'They are kept, not published, while the source is private.</p>'
                '<p class="hint">Until then the demo below is the way to try obsmage, and it needs nothing installed.</p>')
    return ('<section class="sec" id="releases" aria-labelledby="rel-h"><h2 id="rel-h">Releases</h2>%s</section>' % body)


def page_index(conf, facts, have_topology, rev, day):
    c = facts["counts"]
    first = "topology/topoforge/index.html?load=/drawings/obsmage.json"
    if have_topology:
        stage = ('<div class="stage-app"><iframe id="topology" class="topology" loading="lazy" title="The obsmage drawing, in topology forge" '
                 'src="%s&amp;embed=bare,ready"></iframe>'
                 '<p class="hint stage-note">Drag to move about, scroll to zoom, click a part for what it does. '
                 '<a href="%s">Open it full size</a>, where every shape can be moved, changed and saved.</p></div>' % (e(first, quote=True), e(first, quote=True)))
    else:
        stage = '<p class="hint">This build had no topology checkout, so the drawing app is not here; the figure shows the same picture.</p>'
    split_demo = "\n".join(e(x) for x in ["[Video]", facts["video"][0], facts["video"][1]])
    atom_demo = "\n".join(e("basic.ini/Video/" + x) for x in facts["video"])
    secret_line = e([x for x in facts["twitch"] if x.startswith("Token=")][0])
    parts = [
        ("Atoms", "Every OBS setting becomes one line: a key and its value, in a file of its own set. Read it, compare it, keep it in git. "
                  "Join the atoms and you get the OBS files back exactly: INI byte for byte, JSON the way OBS reads it."),
        ("Credentials stay home", "Stream keys, tokens and passwords become <code>@secret(len=N)</code> wherever atoms are shared. "
                                  "Their values live in a vault on your own machine, readable by you alone."),
        ("Screen maps that keep up", "The composer finds screen captures bound by position number, which point at the wrong screen when one is "
                                     "unplugged, and binds them by the screen's own id. It keeps your hand placement, and hides what it would otherwise delete."),
        ("A healer that follows main", "A small timer fetches the newest code, builds the package and the OBS plugin, and writes down every run. "
                                       "It builds; installing stays your decision."),
    ]
    cards = "".join('<li class="card"><h3>%s</h3><p>%s</p></li>' % (e(t), d) for t, d in parts)
    body = (head("obsmage: OBS Studio kept as plain words",
                 "obsmage keeps every OBS Studio setting as a key and a value you can read, compare and keep, and joins them back exactly. Try it in your browser.",
                 "index") +
            '<main id="main">\n'
            '<section class="hero" aria-labelledby="hero-h"><div class="hero-words">'
            '<p class="kicker">OBS Studio, kept as plain words</p>'
            '<h1 id="hero-h">Every setting a line you can read.</h1>'
            '<p class="lede">obsmage splits a whole OBS setup into atoms (one key, one value each) and joins them back exactly. '
            'Change a scene by hand, review it like code, move it to a new machine. Credentials never leave yours.</p>'
            '<p class="cta"><a class="button" href="demo.html">Try it in your browser</a> '
            '<span class="hint">An invented setup, or your own files. Nothing is sent anywhere.</span></p></div>'
            '<figure class="splitfig" aria-labelledby="splitfig-c"><div class="sf-col"><span class="sf-k">basic.ini</span>'
            '<pre class="sf-pre">%s</pre></div><div class="sf-arrow" aria-hidden="true">→</div>'
            '<div class="sf-col"><span class="sf-k">atoms (profile Sample_Studio)</span><pre class="sf-pre sf-atoms">%s\n<span class="sf-secret">basic.ini/Twitch/%s</span></pre></div>'
            '<figcaption id="splitfig-c" class="hint">From the demo\'s sample: %d atoms in %d files, %d credentials withheld; '
            'joined back, identical (counted by omg_atoms.py when this page was built, %s).</figcaption></figure></section>\n'
            % (split_demo, atom_demo, secret_line, facts["atoms"], len(facts["files"]), c["secret"], day) +
            '<section class="sec stage" id="picture" aria-labelledby="pic-h"><h2 id="pic-h">The picture</h2>'
            '<p class="lede">How the parts fit, drawn in topology forge, the same drawing app that opens corwin.cloud.</p>'
            '%s<figure class="flowfig">%s<figcaption class="hint">OBS writes its files; obsmage splits them into atoms; '
            'the composer and the healer work from the atoms; releases come out of the healer\'s builds.</figcaption></figure></section>\n'
            % (stage, flow_svg(conf)) +
            '<section class="sec" id="parts" aria-labelledby="parts-h"><h2 id="parts-h">What it does</h2><ul class="cards">%s</ul></section>\n' % cards +
            releases_section(conf) + "\n" +
            '<section class="sec" id="why" aria-labelledby="why-h"><h2 id="why-h">Why it is made this way</h2>'
            '<p>A streaming setup is work people do with their hands and their time. It should belong to them in a form they can read, '
            'not only in a program\'s private files. So obsmage is free software: run it, read it, change it, share it.</p>'
            '<ul class="plain"><li>No account, no telemetry. It runs on your own machine.</li>'
            '<li>Nothing is reorganised for you. The tools point out a pattern; a person decides.</li>'
            '<li>Built on OBS Studio as it is, with changes offered back to it.</li>'
            '<li>This site works by keyboard, at phone width, in light and dark, and loads nothing from any other host.</li></ul></section>\n'
            '<section class="sec" id="made" aria-labelledby="made-h"><h2 id="made-h">How this page was made</h2>'
            '<p>A short Python script builds it as plain files, the way <a href="%s">corwin.cloud</a> is built '
            '(<a href="%s">its source</a>): no framework, no tracking, no fonts or scripts from another host, and a policy that forbids them. '
            'The drawing app is <a href="%s">topology</a>, staged from its own checkout at build time. '
            'The demo is new JavaScript that reads and writes the same atoms as obsmage\'s Python tools; its tests run both on the same files and compare them byte for byte. '
            'The release feed has the shape of <a href="%s">about-corwin</a>\'s channel. nginx serves it all from gw33, a ghostwheel host.</p>'
            '<p>The source of obsmage and of this page is <a href="%s">inputloop/obsmage</a> (the page is its <code>site/</code> folder). '
            'For a real setup kept this way, see <a href="%s">inputloop/obsmage-corwin</a>: one person\'s OBS recipe as atoms, '
            'every credential withheld.</p></section>\n'
            % (PUBLIC["corwin.cloud site"], PUBLIC["corwin.cloud"], PUBLIC["topology"], PUBLIC["about-corwin"], PUBLIC["obsmage"], PUBLIC["obsmage-corwin"]) +
            '</main>\n<script src="js/front.js"></script>\n' + foot(rev, day))
    return body


def page_demo(facts, rev, day):
    sample = json.dumps({"files": facts["sample_files"], "displays": facts["displays"]}, ensure_ascii=True)
    return (head("Try obsmage: an OBS setup as atoms, in your browser",
                 "Split an invented OBS setup into atoms, edit one, and watch the OBS file come back exactly. Bring your own files: they stay in your browser.",
                 "demo") +
            '<main id="main" class="demo">\n'
            '<section class="demo-intro" aria-labelledby="demo-h"><h1 id="demo-h">An OBS setup, as atoms</h1>'
            '<p class="lede">This is an invented setup: a profile, three screens and a scene collection, with made-up credentials. '
            'Change any atom, or drag a screen on the map, and the OBS file beside it is joined again from the atoms. Everything happens in this page; it sends nothing.</p>'
            '<p class="status" id="rt" role="status" aria-live="polite">Scripts are off, so the demo cannot run. The sample\'s files are listed below.</p></section>\n'
            '<div class="demo-grid js-only" id="demo">\n'
            '<section class="pane" aria-labelledby="atoms-h"><h2 id="atoms-h">Atoms</h2>'
            '<label class="field">Set <select id="set-pick"></select></label>'
            '<p class="hint" id="set-what"></p>'
            '<div id="atom-list" class="atom-list" role="group" aria-labelledby="atoms-h"></div></section>\n'
            '<section class="pane" aria-labelledby="file-h"><h2 id="file-h">The OBS file, joined</h2>'
            '<div class="row"><label class="field">File <select id="file-pick"></select></label>'
            '<label class="check"><input type="checkbox" id="reveal"> Show withheld values</label></div>'
            '<pre id="file-view" class="file-view" tabindex="0" aria-label="The joined file"></pre></section>\n'
            '<section class="pane pane-wide" aria-labelledby="map-h"><h2 id="map-h">Screen map</h2>'
            '<p class="hint">Left, the screens as they sit on the desk; right, the <em>Screenmap</em> scene that shows them. '
            'Drag a screen on the scene, or focus it and use the arrow keys (Shift for bigger steps).</p>'
            '<div class="maps"><svg id="desk" class="map" role="img" aria-labelledby="desk-t"><title id="desk-t">The screens, as placed on the desk</title></svg>'
            '<svg id="scene" class="map" role="group" aria-labelledby="scene-t"><title id="scene-t">The Screenmap scene</title></svg></div>'
            '<ul id="audit" class="audit"></ul>'
            '<div class="row"><button type="button" id="bind">Propose stable ids</button></div>'
            '<div id="plan" class="plan" hidden></div></section>\n'
            '<section class="pane pane-wide" aria-labelledby="own-h"><h2 id="own-h">Your own files (they stay in this browser)</h2>'
            '<p class="hint">Choose OBS files (a profile\'s <code>basic.ini</code>, <code>service.json</code>, a scene collection\'s <code>.json</code>, '
            '<code>global.ini</code> or <code>user.ini</code>) or paste one. They are read here, by this page\'s own script, and never sent: '
            'this page\'s policy forbids it any connection at all. Credentials are withheld as they would be in obsmage.</p>'
            '<div class="row"><label class="field">Files <input type="file" id="own-files" multiple accept=".ini,.json"></label></div>'
            '<div class="row"><label class="field grow">Or paste, as <select id="own-kind"><option value="basic/profiles/Mine/basic.ini">a profile\'s basic.ini</option>'
            '<option value="basic/profiles/Mine/service.json">service.json</option><option value="basic/scenes/Mine.json">a scene collection</option>'
            '<option value="global.ini">global.ini</option></select></label></div>'
            '<textarea id="own-text" rows="6" spellcheck="false" aria-label="Paste an OBS file here"></textarea>'
            '<div class="row"><button type="button" id="own-go">Split these</button> <button type="button" id="sample-go">Back to the sample</button></div>'
            '<p class="hint" id="own-say" role="status" aria-live="polite"></p></section>\n'
            '</div>\n'
            '<noscript><section class="pane"><h2>The sample\'s files</h2><ul>%s</ul>'
            '<p>With scripts on, this page splits them into atoms and joins them back. Its script is free software (<a href="jslicense.html">licences</a>).</p></section></noscript>\n'
            '<script id="sample" type="application/json">%s</script>\n'
            '</main>\n<script src="js/omg-atoms.js"></script>\n<script src="js/omg-compose.js"></script>\n<script src="js/demo.js"></script>\n'
            % ("".join("<li><code>%s</code></li>" % e(f) for f in facts["files"]), sample.replace("</", "<\\/")) + foot(rev, day))


def page_colophon(rev, day):
    rows = [
        ("obsmage", "the atom layer, the composer, the healer and this site", "INPUTLOOP (Corwin Brust and Bryant Frankford)",
         "code GPL-3.0-or-later OR LGPL-3.0-or-later; words CC-BY-SA-4.0", PUBLIC["obsmage"]),
        ("topology forge (formerly TopoForge)", "the drawing app on the front page", "Bryant Frankford, for Corwin; carried on in topology",
         "GPL-3.0-or-later OR LGPL-3.0-or-later", PUBLIC["topology"]),
        ("corwin.cloud", "the way this site is built and deployed", "INPUTLOOP", "GPL-3.0-or-later OR LGPL-3.0-or-later", PUBLIC["corwin.cloud"]),
        ("about-corwin", "the shape of the release channel feed", "Corwin Brust and contributors", "GPL-3.0-or-later", PUBLIC["about-corwin"]),
        ("egad", "the colours (light and dark), from GNU Emacs's Modus themes by Protesilaos Stavrou", "Corwin Brust",
         "GPL-3.0-or-later; Modus themes GPL-3.0-or-later", None),
        ("osifont", "the lettering of headings and the title block", "Zefram Cochrane and osifont contributors",
         "GPL-3.0 with the font exception", None),
        ("IBM Plex Sans Condensed", "the small capitals of the title block", "IBM", "SIL Open Font License 1.1", None),
        ("OBS Studio", "what all of this is for", "the OBS Project and its contributors", "GPL-2.0-or-later", PUBLIC["obs"]),
    ]
    trs = "".join('<tr><th scope="row">%s</th><td>%s</td><td>%s</td><td>%s</td></tr>' % (
        ('<a href="%s">%s</a>' % (u, e(n))) if u else e(n), e(what), e(who), e(lic)) for n, what, who, lic, u in rows)
    return (head("Colophon: obsmage.com", "Who made the parts of obsmage.com, and under which licences.", "colophon") +
            '<main id="main" class="narrow"><h1>Colophon</h1>'
            '<p class="lede">What this site is made of, who made each part, and the licence each is under. '
            'The licence texts are served beside the site in <a href="LICENSES/">LICENSES/</a>.</p>'
            '<div class="table-wrap"><table><caption class="visually-hidden">Credits and licences</caption>'
            '<thead><tr><th scope="col">Part</th><th scope="col">What it does here</th><th scope="col">Made by</th><th scope="col">Licence</th></tr></thead>'
            '<tbody>%s</tbody></table></div>'
            '<h2>The demo\'s sample</h2><p>Invented from end to end: no real profile, screens, devices, hosts or credentials. '
            'The made-up credentials start with FAKE; the host is <code>example.invalid</code>, a name reserved never to resolve.</p>'
            '<h2>Written with</h2><p>Mentat (for Corwin, claude-opus-5-5) wrote this site\'s code and words at Corwin\'s request; '
            'Corwin decides what ships.</p></main>\n' % trs + foot(rev, day))


def page_jslicense(rev, day):
    rows = [("js/look.js", "GPL-3.0-or-later"), ("js/front.js", "GPL-3.0-or-later"), ("js/omg-atoms.js", "GPL-3.0-or-later"),
            ("js/omg-compose.js", "GPL-3.0-or-later"), ("js/demo.js", "GPL-3.0-or-later")]
    trs = "".join('<tr><td><a href="%s">%s</a></td><td><a href="https://www.gnu.org/licenses/gpl-3.0.html">%s</a></td>'
                  '<td><a href="%s">%s</a></td></tr>' % (f, f, l, f, f) for f, l in rows)
    return (head("JavaScript licences: obsmage.com", "The licence of every script on obsmage.com, for GNU LibreJS.", "jslicense") +
            '<main id="main" class="narrow"><h1>JavaScript licences</h1>'
            '<p>Every script on this site is free software, served unminified from this site. Each is offered under GPL-3.0-or-later OR '
            'LGPL-3.0-or-later; the table names the GPL for GNU LibreJS. The drawing app under <code>topology/</code> carries its own labels.</p>'
            '<table id="jslicense-labels1"><tbody>%s</tbody></table></main>\n' % trs + foot(rev, day))


def page_404(rev, day):
    return (head("Not here: obsmage.com", "There is no page at this address.", "404") +
            '<main id="main" class="narrow"><h1>Nothing here</h1><p>There is no page at this address. '
            '<a href="./">The front page</a> has the picture; <a href="demo.html">the demo</a> runs in your browser.</p></main>\n' + foot(rev, day))


# ---- topology staging (corwin.cloud's way) -------------------------------------------------------------

def stage_topology(out, tdir):
    if not tdir or not os.path.isfile(os.path.join(tdir, "bin", "stage-www.sh")):
        print("build: no topology checkout at %r: the front page shows the figure only" % tdir, file=sys.stderr)
        return False
    dest = os.path.join(out, "topology")
    r = subprocess.run(["sh", "bin/stage-www.sh", dest], cwd=tdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if r.returncode != 0:
        print("build: stage-www.sh failed (%s)" % r.stderr.strip(), file=sys.stderr)
        return False
    shutil.rmtree(os.path.join(dest, "context"), ignore_errors=True)   # that branch's working notes are for its own host
    pat = re.compile(r"https://github\.com/[\w.-]+/(?:%s)(?:\.git)?\b" % "|".join(re.escape(n) for n in PRIVATE_NAMES + ["topology-private"]))
    hashes = []
    for dp, _, fs in os.walk(dest):
        for f in fs:
            p = os.path.join(dp, f)
            try:
                t = open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            n = pat.sub("(private repository, not public yet)", t)
            if n != t:
                open(p, "w", encoding="utf-8").write(n)
            if f.endswith(".html"):
                for m in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", n, re.S):
                    h = "'sha256-%s'" % base64.b64encode(hashlib.sha256(m.group(1).encode("utf-8")).digest()).decode()
                    if h not in hashes:
                        hashes.append(h)
    hashes.sort()
    policy = ("default-src 'self'; script-src 'self' %s; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
              "font-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; "
              "form-action 'none'; frame-ancestors 'self'" % " ".join(hashes))
    write(GEN, "topology-csp.conf",
          "# generated by site/build.py: the policy for /topology/ (its inline scripts, by hash; no other host)\n"
          "add_header Content-Security-Policy \"%s\" always;\n" % policy)
    return True


def releases_snippet(conf):
    """What nginx includes for /dist/. Closed: nothing is mapped, so /dist/ is a 404."""
    if conf["releases"] == "open":
        return ("# generated by site/build.py: releases are OPEN (site.conf)\n"
                "location ^~ /dist/ {\n    alias /var/lib/obsmage-dist/public/;\n    autoindex on;\n"
                "    default_type application/octet-stream;\n    types { application/json json; text/plain txt; }\n"
                "    add_header Cache-Control \"no-cache\" always;\n    add_header Content-Security-Policy \"default-src 'none'\" always;\n"
                "    add_header X-Content-Type-Options \"nosniff\" always;\n}\n")
    return "# generated by site/build.py: releases are CLOSED (site.conf); nothing under /dist/ is served\n"


def write(d, name, text):
    p = os.path.join(d, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(SITE, "public"))
    ap.add_argument("--topology", default=os.environ.get("TOPOLOGY_DIR", os.path.join(TOP, "..", "topology")))
    ap.add_argument("--conf", default=None, help="a site.conf other than site/site.conf (tests)")
    ap.add_argument("--generated", default=os.path.join(SITE, "generated"), help="where the nginx snippets go")
    a = ap.parse_args()
    global GEN
    GEN = a.generated
    conf = read_conf(a.conf)
    out = a.out
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    rev, day = revision()
    facts = sample_facts()
    cfg = os.path.join(SITE, "sample", "config")
    facts["sample_files"] = {rel: open(os.path.join(cfg, rel), encoding="utf-8", newline="").read() for rel in facts["files"]}
    facts["displays"] = json.load(open(os.path.join(SITE, "sample", "displays.json"), encoding="utf-8"))
    have = stage_topology(out, a.topology)
    if not have:
        write(GEN, "topology-csp.conf", "# generated by site/build.py: no topology staged\n")
    for sub in ("css", "js", "fonts"):
        shutil.copytree(os.path.join(SITE, "src", sub), os.path.join(out, sub))
    shutil.copyfile(os.path.join(SITE, "src", "favicon.svg"), os.path.join(out, "favicon.svg"))
    shutil.copyfile(os.path.join(SITE, "src", "robots.txt"), os.path.join(out, "robots.txt"))
    shutil.copytree(os.path.join(SITE, "LICENSES"), os.path.join(out, "LICENSES"))
    lic = sorted(f for f in os.listdir(os.path.join(SITE, "LICENSES")) if f.endswith(".txt"))
    write(out, "LICENSES/index.html", head("Licence texts: obsmage.com", "The licence texts this site's parts are under.", "licenses")
          .replace('href="css/', 'href="../css/').replace('src="js/', 'src="../js/').replace('href="favicon', 'href="../favicon')
          .replace('href="./"', 'href="../"').replace('href="demo.html"', 'href="../demo.html"').replace('href="./#', 'href="../#')
          .replace('href="colophon.html"', 'href="../colophon.html"') +
          '<main id="main" class="narrow"><h1>Licence texts</h1><ul>%s</ul><p><a href="../colophon.html">Which part is under which</a>.</p></main>\n'
          % "".join('<li><a href="%s">%s</a></li>' % (e(f), e(f[:-4])) for f in lic) +
          foot(rev, day).replace('href="colophon.html"', 'href="../colophon.html"').replace('href="jslicense.html"', 'href="../jslicense.html"'))
    write(out, "drawings/obsmage.json", json.dumps(drawing(conf), indent=1) + "\n")
    write(out, "index.html", page_index(conf, facts, have, rev, day))
    write(out, "demo.html", page_demo(facts, rev, day))
    write(out, "colophon.html", page_colophon(rev, day))
    write(out, "jslicense.html", page_jslicense(rev, day))
    write(out, "404.html", page_404(rev, day))
    write(GEN, "releases.conf", releases_snippet(conf))
    print("build: wrote %s (topology %s, releases %s, sample %d atoms)" % (out, "staged" if have else "absent", conf["releases"], facts["atoms"]))


if __name__ == "__main__":
    main()

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
