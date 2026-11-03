#!/usr/bin/env python3
"""secret-scan.py: refuse a bundle that carries a credential. Run by omg-dist on every tarball and
every Debian package (unpacked) before anything is staged; exit 1 stops the release.

    secret-scan.py DIR          prints one line per finding (file, line, rule; never the value)

Two rules, so a credential has to get past both:
  1. atoms: in every .kv file of an atom store, an atom whose key omg_atoms.py classes as a secret
     must read @secret(len=N) (INI) or "@secret(len=N)" (typed JSON), or be empty;
  2. shapes: no file may hold something shaped like a live credential (a private key block, a
     GitHub, GitLab, Slack, AWS or OpenAI-style token, a Twitch stream key), unless the line says
     FAKE, which is how this tree marks its made-up test credentials.
Standard library only; omg_atoms.py is read from beside this script's tree or from OMG_TOOLS.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("OMG_TOOLS", os.path.join(HERE, "..", "..", "tools")))
import omg_atoms as A  # noqa: E402

SHAPES = [
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("API secret key", re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}\b")),
    ("Twitch stream key", re.compile(r"\blive_[0-9]{6,}_[A-Za-z0-9]{20,}\b")),
]
WITHHELD = re.compile(r'^"?@secret\(len=\d+\)"?$')


def scan(root):
    found = []
    for dp, dirs, fs in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in sorted(fs):
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root)
            try:
                with open(p, "rb") as fh:
                    data = fh.read()
            except OSError:
                continue
            text = data.decode("utf-8", "replace")
            for n, line in enumerate(text.split("\n"), 1):
                if "FAKE" in line:
                    continue
                for name, rx in SHAPES:
                    if rx.search(line):
                        found.append("%s:%d: %s" % (rel, n, name))
            if f.endswith(".kv") and "/atoms/" in "/" + rel.replace(os.sep, "/"):
                try:
                    rows = A.parse_kv(text)
                except ValueError:
                    continue
                for k, v, typed in rows:
                    if A.classify(k, v) == "secret" and not WITHHELD.match(v):
                        found.append("%s: atom %s is a credential and is not withheld" % (rel, k))
    return found


def main():
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        print("usage: secret-scan.py DIR", file=sys.stderr)
        return 2
    found = scan(sys.argv[1])
    for x in found:
        print(x)
    print("secret-scan: %s" % ("%d finding(s): REFUSED" % len(found) if found else "clean"), file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin, claude-opus-5-5)
