#!/usr/bin/env python3
"""chan_check.py: check a channel feed (channel/1, c4 d/channels/SPEC.md) as omg-dist writes it.

    chan_check.py FEED [--dir DIR]    exit 0 valid; 1 invalid (one line says why)

The line form (one "name": "value" per line, two spaces, braces alone, a comma after every field
but the last, printable ASCII only), the required fields and their rules, and obsmage's own
fields: deb, deb_sha256 and deb_size, all three or none. With --dir, the bundles the feed names
must be there and their sha256 and size must match. Standard library only.
"""
import hashlib
import os
import re
import sys

RULES = {
    "format": lambda v: v == "channel/1",
    "channel": lambda v: re.fullmatch(r"[a-z][a-z0-9-]{0,40}", v),
    "revision": lambda v: re.fullmatch(r"[0-9a-f]{7,64}", v),
    "stamp": lambda v: re.fullmatch(r"[0-9]{8}-[0-9]{6}", v),
    "artifact": lambda v: ".." not in v and (re.fullmatch(r"https://[A-Za-z0-9._~:/?&=%@+,-]{1,292}", v)
                                            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{6,119}", v) and v.endswith(".tar.gz")),
    "sha256": lambda v: re.fullmatch(r"[0-9a-f]{64}", v),
    "key": lambda v: re.fullmatch(r"[A-Za-z0-9._:+-]{1,160}", v),
    "size": lambda v: re.fullmatch(r"[0-9]{1,12}", v),
    "inputs": lambda v: len(v) <= 200,
    "deb": lambda v: ".." not in v and re.fullmatch(r"obsmage_[A-Za-z0-9.+~-]+_[a-z0-9]+\.deb", v),
    "deb_sha256": lambda v: re.fullmatch(r"[0-9a-f]{64}", v),
    "deb_size": lambda v: re.fullmatch(r"[0-9]{1,12}", v),
}
REQUIRED = ["format", "channel", "revision", "stamp", "artifact", "sha256", "key"]


def check(path, d=None):
    with open(path, "rb") as fh:
        raw = fh.read()
    if re.search(rb"[^\x20-\x7e\n]", raw):
        return "not printable ASCII"
    lines = raw.decode("ascii").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) < 3 or lines[0] != "{" or lines[-1] != "}":
        return "not the line form"
    body, fields = lines[1:-1], {}
    for i, ln in enumerate(body):
        m = re.fullmatch(r'  "([a-z][a-z0-9_]*)": "([^"\\]*)"(,?)', ln)
        if not m:
            return "line %d: not the line form" % (i + 2)
        if (m.group(3) == ",") != (i < len(body) - 1):
            return "line %d: comma" % (i + 2)
        if m.group(1) in fields:
            return "duplicate field " + m.group(1)
        fields[m.group(1)] = m.group(2)
    for k in REQUIRED:
        if k not in fields:
            return "missing " + k
    for k, v in fields.items():
        if k in RULES and not RULES[k](v):
            return "bad " + k
    debs = [k for k in ("deb", "deb_sha256", "deb_size") if k in fields]
    if debs and len(debs) != 3:
        return "deb, deb_sha256 and deb_size go together"
    if d:
        art = fields["artifact"].rsplit("/", 1)[-1]
        for f, sha, size in [(art, fields["sha256"], fields.get("size"))] + ([(fields["deb"], fields["deb_sha256"], fields["deb_size"])] if debs else []):
            p = os.path.join(d, f)
            if not os.path.isfile(p):
                return "%s is not beside the feed" % f
            with open(p, "rb") as fh:
                data = fh.read()
            if hashlib.sha256(data).hexdigest() != sha:
                return "%s: sha256 does not match" % f
            if size is not None and str(len(data)) != size:
                return "%s: size does not match" % f
    return None


def main():
    a = sys.argv[1:]
    d = None
    if "--dir" in a:
        i = a.index("--dir")
        d = a[i + 1]
        del a[i:i + 2]
    if len(a) != 1:
        print("usage: chan_check.py FEED [--dir DIR]", file=sys.stderr)
        return 64
    why = check(a[0], d)
    if why:
        print("chan_check: " + why)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
