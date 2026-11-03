#!/usr/bin/env python3
"""omg_atoms -- obsmage's key/value atom layer over a whole OBS configuration.

    omg_atoms.py find                         where OBS keeps its configuration on this machine
    omg_atoms.py split CONFIG ATOMS [--vault F] [--ledger DIR]   OBS files -> atoms
    omg_atoms.py join  ATOMS OUT    [--vault F]                  atoms -> OBS files
    omg_atoms.py verify CONFIG                lossless round trip, in a temp dir
    omg_atoms.py rollup ATOMS STAGES.md       atoms -> the single-file roll-up
    omg_atoms.py unroll STAGES.md ATOMS       the roll-up -> atoms (stops on a two-sided conflict)
    omg_atoms.py suggest LEDGER [--min N]     atoms that keep changing together (never moves them)
    omg_atoms.py classes ATOMS                count atoms by class

A CONFIG is an OBS configuration root (the folder holding basic/, global.ini, user.ini).
An atom is one key and its value: <stage>/<file>/<set>.kv holds one set's keys, in order.
Classes: plain, path, device, secret. A secret's value goes to the vault (git-ignored,
mode 600) and the atom keeps only @secret(len=N). Nothing published ever carries the value.

INI files round-trip byte for byte (a _shape file keeps section order, blank lines, comments,
BOM and line endings). JSON files round-trip parse-equal, and re-serialize the way OBS writes
them (4-space indent).

Exit: 0 ok; 1 a check failed (verify mismatch, unroll conflict, missing vault value); 2 usage.
"""
import argparse, hashlib, json, os, re, shutil, sys, tempfile, time

SECRET_KEY = re.compile(
    r'(?i)^(token|refreshtoken|refresh_token|access_token|authsecret|authsalt|password|passwd|'
    r'key|stream_?key|secret|.*_secret|.*_token|bearer.*|server_?password|apikey|api_key)$')
DEVICE_KEY = re.compile(r'(?i)^(monitor_id|device_id|video_device_id|audio_device_id|'
                        r'monitoringdeviceid|uuid|cookieid|monitor_wgc)$')
PATH_VAL = re.compile(r'^([A-Za-z]:\\|/home/|/Users/|~/|\\\\)')
PLACEHOLDER = re.compile(r'^@secret\(len=(\d+)\)$')


# ---------- classification ----------------------------------------------------------------

def classify(key, value):
    last = key.rstrip('/').split('/')[-1].lstrip('#')
    if SECRET_KEY.match(last) and value not in ('', '""', 'null', '[]', '{}'):
        return 'secret'
    if DEVICE_KEY.match(last) or value.startswith('\\\\?\\') or value.startswith('"\\\\\\\\?\\\\'):
        return 'device'
    v = value[1:] if value.startswith('"') else value
    if PATH_VAL.match(v):
        return 'path'
    return 'plain'


# ---------- .kv encoding ------------------------------------------------------------------
# key=value      raw (INI)        key:=<json>   typed (JSON files)
# keys escape % = and newline as %25 %3D %0A.

def enc_key(k):
    return k.replace('%', '%25').replace('=', '%3D').replace('\n', '%0A').replace(':', '%3A')

def dec_key(k):
    return k.replace('%3A', ':').replace('%0A', '\n').replace('%3D', '=').replace('%25', '%')

def kv_line(key, value, typed):
    return f'{enc_key(key)}{":=" if typed else "="}{value}'

def parse_kv(text):
    out = []
    for line in text.split('\n'):
        if not line:
            continue
        i = line.index('=')
        typed = i > 0 and line[i - 1] == ':'
        k = line[:i - 1] if typed else line[:i]
        out.append((dec_key(k), line[i + 1:], typed))
    return out


# ---------- INI ---------------------------------------------------------------------------

def split_ini(data):
    """bytes -> (meta, shape lines, {set: [(key, value)]})"""
    bom = data.startswith(b'\xef\xbb\xbf')
    text = data[3:].decode('utf-8') if bom else data.decode('utf-8')
    # Line endings: OBS sometimes appends a CRLF line to an LF file (seen on Avalon), so a file
    # can mix them. 'crlf' says every ending is CRLF; 'eols' (only when mixed) lists each line's
    # ending, N for LF, C for CRLF, for the last line too (N when it has none).
    parts = re.split(r'(\r\n|\n)', text)
    lines, ends = parts[0::2], [('C' if e == '\r\n' else 'N') for e in parts[1::2]]
    crlf = bool(ends) and all(e == 'C' for e in ends)
    mixed = 'C' in ends and 'N' in ends
    trailing = lines[-1] == ''
    if trailing:
        lines = lines[:-1]
    shape, sets, cur = [], {}, '_head'
    for ln in lines:
        m = re.match(r'^\[(.*)\]$', ln)
        if m:
            cur = m.group(1)
            sets.setdefault(cur, [])
            shape.append('S ' + cur)
        elif '=' in ln and not ln.lstrip().startswith((';', '#')):
            k, v = ln.split('=', 1)
            sets.setdefault(cur, []).append((k, v))
            shape.append('K ' + enc_key(k))
        else:
            shape.append('R ' + ln)
    meta = {'bom': bom, 'crlf': crlf, 'trailing': trailing}
    if mixed:
        meta['eols'] = ''.join(ends)
    return meta, shape, sets

def join_ini(meta, shape, sets):
    pos, cur, out = {}, '_head', []
    for s in shape:
        tag, rest = s[0], s[2:]
        if tag == 'S':
            cur = rest
            out.append(f'[{rest}]')
        elif tag == 'K':
            k = dec_key(rest)
            idx = pos.get((cur, k), 0)
            vals = [v for kk, v in sets[cur] if kk == k]
            out.append(f'{k}={vals[idx]}')
            pos[(cur, k)] = idx + 1
        else:
            out.append(rest)
    if meta.get('eols'):
        e = meta['eols']
        text = ''.join(l + (('\r\n' if e[i] == 'C' else '\n') if i < len(e) else '')
                       for i, l in enumerate(out))
    else:
        nl = '\r\n' if meta['crlf'] else '\n'
        text = nl.join(out) + (nl if meta['trailing'] else '')
    data = text.encode('utf-8')
    return (b'\xef\xbb\xbf' + data) if meta['bom'] else data


# ---------- JSON --------------------------------------------------------------------------
# Pointer segments: dict key -> escaped key; list index -> '#N'. Empty containers are leaves.

def esc_seg(s):
    s = s.replace('~', '~0').replace('/', '~1')
    return '~h' + s[1:] if s.startswith('#') else s

def unesc_seg(s):
    if s.startswith('~h'):
        s = '#' + s[2:]
    return s.replace('~1', '/').replace('~0', '~')

def flatten(obj, prefix=''):
    if isinstance(obj, dict) and obj:
        for k, v in obj.items():
            yield from flatten(v, prefix + '/' + esc_seg(k))
    elif isinstance(obj, list) and obj:
        for i, v in enumerate(obj):
            yield from flatten(v, f'{prefix}/#{i}')
    else:
        yield prefix, json.dumps(obj, ensure_ascii=False)

def unflatten(pairs):
    root = None
    for ptr, raw in pairs:
        val = json.loads(raw)
        segs = ptr.split('/')[1:]
        if not segs:
            return val
        if root is None:
            root = [] if segs[0].startswith('#') else {}
        node = root
        for i, seg in enumerate(segs):
            last = i == len(segs) - 1
            nxt = None if last else ([] if segs[i + 1].startswith('#') else {})
            if seg.startswith('#'):
                n = int(seg[1:])
                while len(node) <= n:
                    node.append(None)
                if last:
                    node[n] = val
                else:
                    if node[n] is None:
                        node[n] = nxt
                    node = node[n]
            else:
                k = unesc_seg(seg)
                if last:
                    node[k] = val
                else:
                    node = node.setdefault(k, nxt)
    return root

def json_sets(obj):
    """Scene collections: one set per source; everything else one set."""
    sets = {}
    if isinstance(obj, dict) and isinstance(obj.get('sources'), list):
        for k, v in obj.items():
            if k == 'sources':
                for i, src in enumerate(v):
                    name = src.get('name', '') if isinstance(src, dict) else ''
                    sid = f'sources/{i:03d}-{safe(name)}'
                    sets[sid] = [(f'/sources/#{i}' + p, r) for p, r in flatten(src)]
                    if not sets[sid]:
                        sets[sid] = [(f'/sources/#{i}', '{}')]
            else:
                sets.setdefault('_top', []).extend(flatten(v, '/' + esc_seg(k)))
    else:
        sets['_all'] = list(flatten(obj))
    return sets

def safe(name):
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', name).strip('_')[:48]
    return s or 'unnamed'

def dump_obs_json(obj):
    return (json.dumps(obj, indent=4, ensure_ascii=False) + '\n').encode('utf-8')


# ---------- the atom store ----------------------------------------------------------------

def config_files(root):
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in ('logs', 'crashes', 'updates', 'profiler_data',
                                                      'plugin_manager', '.omg'))
        for f in sorted(files):
            if f.endswith(('.ini', '.json')) and not f.endswith('.bak'):
                yield os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, '/')

def read_text(path):
    """UTF-8, newlines untouched (text mode would turn a lone CR in a value into LF)."""
    with open(path, encoding='utf-8', newline='') as fh:
        return fh.read()

def write_text(path, text):
    if os.path.dirname(path):  # a bare file name means the current directory
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)

def load_vault(path):
    v = {}
    if path and os.path.exists(path):
        for k, val, _ in parse_kv(read_text(path)):
            v[k] = val
    return v

IS_WINDOWS = os.name == 'nt'

def lock_file_to_owner(path):
    """Windows ignores the 0o600 in os.open, so say it with an ACL: drop inherited rights and
    grant the current user alone. Returns True when icacls reported success; otherwise warns
    (on stderr, once per call) and the vault keeps whatever its folder's rights give it."""
    import subprocess
    user = os.environ.get('USERNAME') or os.environ.get('USER') or ''
    try:
        r = subprocess.run(['icacls', path, '/inheritance:r', '/grant:r', user + ':F'],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if user and r.returncode == 0:
            return True
    except OSError:
        pass
    sys.stderr.write('warning: could not restrict %s to its owner (icacls failed); its folder\'s '
                     'rights apply. Keep the vault out of shared folders.\n' % path)
    return False

def save_vault(path, vault):
    if not path or not vault:
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    if IS_WINDOWS:  # lock it while it is still empty, then write the secrets
        lock_file_to_owner(path)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as fh:
        for k in sorted(vault):
            fh.write(kv_line(k, vault[k], False) + '\n')

def read_store(atoms):
    """-> {atom path: value}"""
    out = {}
    for dirpath, _, files in os.walk(atoms):
        for f in files:
            if f.endswith('.kv'):
                p = os.path.join(dirpath, f)
                rel = os.path.relpath(p, atoms).replace(os.sep, '/')[:-3]
                for k, v, _ in parse_kv(read_text(p)):
                    out[rel + '|' + k] = v
    return out

def store_hash(atoms):
    h = hashlib.sha256()
    for dirpath, dirs, files in sorted(os.walk(atoms)):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(dirpath, f)
            h.update(os.path.relpath(p, atoms).replace(os.sep, '/').encode() + b'\0')
            h.update(open(p, 'rb').read() + b'\0')
    return h.hexdigest()

def split(config, atoms, vault_path=None, ledger=None):
    before = read_store(atoms) if os.path.isdir(atoms) else {}
    if os.path.isdir(atoms):
        shutil.rmtree(atoms)
    vault = load_vault(vault_path)
    counts = {'plain': 0, 'path': 0, 'device': 0, 'secret': 0}
    for rel in config_files(config):
        data = open(os.path.join(config, rel), 'rb').read()
        base = os.path.join(atoms, rel)
        if rel.endswith('.ini'):
            meta, shape, sets = split_ini(data)
            write_text(os.path.join(base, '_shape'), json.dumps(meta) + '\n' + '\n'.join(shape) + '\n')
            order = []
            for sname, pairs in sets.items():
                order.append(sname)
                lines = []
                for k, v in pairs:
                    cls = classify(k, v); counts[cls] += 1
                    if cls == 'secret':
                        vault[f'{rel}|{sname}|{k}'] = v
                        v = f'@secret(len={len(v)})'
                    lines.append(kv_line(k, v, False))
                write_text(os.path.join(base, safe_set(sname) + '.kv'), '\n'.join(lines) + '\n')
            write_text(os.path.join(base, '_sets'), '\n'.join(order) + '\n')
        else:
            try:
                obj = json.loads(data.decode('utf-8-sig'))
            except ValueError:
                os.makedirs(base, exist_ok=True)
                with open(os.path.join(base, '_raw'), 'wb') as fh:  # bytes, so nothing is lost
                    fh.write(data)
                continue
            sets = json_sets(obj)
            for sname, pairs in sets.items():
                lines = []
                for k, v in pairs:
                    cls = classify(k, v); counts[cls] += 1
                    if cls == 'secret':
                        vault[f'{rel}|{sname}|{k}'] = v
                        v = json.dumps(f'@secret(len={len(json.loads(v)) if v.startswith(chr(34)) else len(v)})')
                    lines.append(kv_line(k, v, True))
                write_text(os.path.join(base, sname + '.kv'), '\n'.join(lines) + '\n')
            write_text(os.path.join(base, '_sets'), '\n'.join(sets) + '\n')
    save_vault(vault_path, vault)
    if ledger:
        record_changes(ledger, before, read_store(atoms))
    return counts

def safe_set(s):
    return 'set-' + (safe(s) if s != '_head' else '_head')

def join(atoms, out, vault_path=None):
    vault = load_vault(vault_path)
    missing = []
    for dirpath, dirs, files in os.walk(atoms):
        if '_raw' in files:  # a .json that is not one JSON document (e.g. JSON lines): kept byte for byte
            dest = os.path.join(out, os.path.relpath(dirpath, atoms))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(os.path.join(dirpath, '_raw'), 'rb') as fh, open(dest, 'wb') as oh:
                oh.write(fh.read())
            continue
        if '_sets' not in files:
            continue
        rel = os.path.relpath(dirpath, atoms).replace(os.sep, '/')
        order = [s for s in read_text(os.path.join(dirpath, '_sets')).split('\n') if s]
        dest = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if rel.endswith('.ini'):
            sh = read_text(os.path.join(dirpath, '_shape')).split('\n')
            meta, shape = json.loads(sh[0]), [s for s in sh[1:] if s]
            sets = {}
            for sname in order:
                pairs = []
                for k, v, _ in parse_kv(read_text(os.path.join(dirpath, safe_set(sname) + '.kv'))):
                    if PLACEHOLDER.match(v):
                        key = f'{rel}|{sname}|{k}'
                        if key not in vault:
                            missing.append(key); continue
                        v = vault[key]
                    pairs.append((k, v))
                sets[sname] = pairs
            if not missing:
                open(dest, 'wb').write(join_ini(meta, shape, sets))
        else:
            pairs = []
            for sname in order:
                for k, v, _ in parse_kv(read_text(os.path.join(dirpath, sname + '.kv'))):
                    if v.startswith('"@secret(len='):
                        key = f'{rel}|{sname}|{k}'
                        if key not in vault:
                            missing.append(key); continue
                        v = vault[key]
                    pairs.append((k, v))
            if not missing:
                open(dest, 'wb').write(dump_obs_json(unflatten(pairs)))
    return missing


# ---------- verify ------------------------------------------------------------------------

def verify(config):
    bad = []
    with tempfile.TemporaryDirectory() as t:
        atoms, vault, out = os.path.join(t, 'atoms'), os.path.join(t, 'vault.kv'), os.path.join(t, 'out')
        split(config, atoms, vault)
        missing = join(atoms, out, vault)
        for rel in config_files(config):
            a = open(os.path.join(config, rel), 'rb').read()
            p = os.path.join(out, rel)
            b = open(p, 'rb').read() if os.path.exists(p) else None
            if rel.endswith('.ini'):
                ok = a == b
            else:
                try:
                    ok = b is not None and json.loads(a.decode('utf-8-sig')) == json.loads(b.decode('utf-8'))
                except ValueError:
                    ok = a == b
            if not ok:
                bad.append(rel)
        # the published side must carry no secret value
        vals = load_vault(vault).values()
        leaks = []
        for dirpath, _, files in os.walk(atoms):
            for f in files:
                text = read_text(os.path.join(dirpath, f))
                leaks += [f for v in vals if len(v) >= 6 and v in text]
    return bad, missing, leaks


# ---------- roll-up -----------------------------------------------------------------------

def rollup(atoms, stages):
    pin = store_hash(atoms)
    out = ['# STAGES', '',
           f'<!-- omg:pin {pin} -->',
           'The single-file roll-up of every obsmage atom. Edit a block below and run',
           '`omg_atoms.py unroll STAGES.md atoms/` to send the change back. Secret values never',
           'appear here (`@secret(len=N)`). Generated; the pin above is the atoms it came from.', '']
    stages_seen = {}
    for dirpath, dirs, files in sorted(os.walk(atoms)):
        dirs.sort()
        rel = os.path.relpath(dirpath, atoms).replace(os.sep, '/')
        for f in sorted(files):
            if f.endswith('.kv'):
                stage = rel.split('/')[0] if '/' in rel else rel
                stages_seen.setdefault(rel, []).append(f)
    for rel in sorted(stages_seen):
        out += [f'## {rel}', '']
        for f in sorted(stages_seen[rel]):
            body = read_text(os.path.join(atoms, rel, f)).rstrip('\n')
            out += [f'```kv set={rel}/{f}', body, '```', '']
    write_text(stages, '\n'.join(out) + '\n')
    return pin

def unroll(stages, atoms):
    text = read_text(stages)
    m = re.search(r'<!-- omg:pin ([0-9a-f]{64}) -->', text)
    if not m:
        return ['no pin in ' + stages]
    blocks = {b.group(1): b.group(2) for b in re.finditer(r'```kv set=(\S+)\n(.*?)\n```', text, re.S)}
    changed = {s: body for s, body in blocks.items()
               if not os.path.exists(os.path.join(atoms, s))
               or read_text(os.path.join(atoms, s)).rstrip('\n') != body}
    if not changed:
        return []
    if store_hash(atoms) != m.group(1):
        return [f'both sides changed since the pin: {s}' for s in sorted(changed)]
    for s, body in changed.items():
        write_text(os.path.join(atoms, s), body + '\n')
    return []


# ---------- ledger + suggest --------------------------------------------------------------

def record_changes(ledger, before, after):
    os.makedirs(ledger, exist_ok=True)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    if not before or not changed:
        return 0
    p = os.path.join(ledger, 'events.tsv')
    seq = len({l.split('\t', 1)[0] for l in open(p, encoding='utf-8')}) if os.path.exists(p) else 0
    ev = time.strftime('%Y-%m-%dT%H:%M:%S') + f'.{seq:06d}'  # unique even within one second
    with open(p, 'a', encoding='utf-8', newline='\n') as fh:
        for k in changed:
            fh.write(f'{ev}\t{k}\n')
    return len(changed)

def suggest(ledger, minimum=3):
    events = {}
    p = os.path.join(ledger, 'events.tsv')
    if not os.path.exists(p):
        return []
    for line in open(p, encoding='utf-8'):
        ev, k = line.rstrip('\n').split('\t', 1)
        events.setdefault(ev, set()).add(k.split('|')[0])  # cluster by set
    pairs = {}
    for sets in events.values():
        s = sorted(sets)
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                pairs[(s[i], s[j])] = pairs.get((s[i], s[j]), 0) + 1
    return sorted(((n, a, b) for (a, b), n in pairs.items() if n >= minimum), reverse=True)


# ---------- find --------------------------------------------------------------------------

def candidates():
    h = os.path.expanduser('~')
    c = []
    if os.environ.get('APPDATA'):
        c.append(os.path.join(os.environ['APPDATA'], 'obs-studio'))
    c += [os.path.join(h, '.config', 'obs-studio'),
          os.path.join(h, '.var', 'app', 'com.obsproject.Studio', 'config', 'obs-studio'),
          os.path.join(h, 'snap', 'obs-studio', 'current', '.config', 'obs-studio'),
          os.path.join(h, 'Library', 'Application Support', 'obs-studio')]
    return [(p, os.path.isdir(os.path.join(p, 'basic'))) for p in c]


def main(argv=None):
    for st in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252; never crash on a name
        try: st.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError): pass
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('find')
    s = sub.add_parser('split'); s.add_argument('config'); s.add_argument('atoms')
    s.add_argument('--vault', default='.omg/vault.kv'); s.add_argument('--ledger')
    j = sub.add_parser('join'); j.add_argument('atoms'); j.add_argument('out')
    j.add_argument('--vault', default='.omg/vault.kv')
    v = sub.add_parser('verify'); v.add_argument('config')
    r = sub.add_parser('rollup'); r.add_argument('atoms'); r.add_argument('stages')
    u = sub.add_parser('unroll'); u.add_argument('stages'); u.add_argument('atoms')
    g = sub.add_parser('suggest'); g.add_argument('ledger'); g.add_argument('--min', type=int, default=3)
    c = sub.add_parser('classes'); c.add_argument('atoms')
    a = ap.parse_args(argv)

    if a.cmd == 'find':
        found = False
        for p, ok in candidates():
            print(('FOUND   ' if ok else 'absent  ') + p); found |= ok
        if not found:
            print('No OBS configuration in the usual places. Name one: omg_atoms.py split PATH ...'
                  ' (the obsmage plugin offers a folder browser here).')
        return 0
    if a.cmd == 'split':
        n = split(a.config, a.atoms, a.vault, a.ledger)
        print('split: ' + ', '.join(f'{v} {k}' for k, v in n.items()) +
              (f'; secret values kept in {a.vault} (mode 600), never in {a.atoms}' if n['secret'] else ''))
        return 0
    if a.cmd == 'join':
        missing = join(a.atoms, a.out, a.vault)
        if missing:
            print('join refused: secret value not in the vault for:'); [print('  ' + m) for m in missing]
            return 1
        print(f'join: wrote {a.out}'); return 0
    if a.cmd == 'verify':
        bad, missing, leaks = verify(a.config)
        for b in bad: print('MISMATCH ' + b)
        for m in missing: print('MISSING  ' + m)
        for l in leaks: print('LEAK     ' + l)
        print('verify: ' + ('ok, lossless and no secret in the atoms' if not (bad or missing or leaks) else 'FAILED'))
        return 1 if (bad or missing or leaks) else 0
    if a.cmd == 'rollup':
        print('rollup: pin ' + rollup(a.atoms, a.stages)); return 0
    if a.cmd == 'unroll':
        errs = unroll(a.stages, a.atoms)
        for e in errs: print('CONFLICT ' + e)
        print('unroll: ' + ('ok' if not errs else 'stopped; nothing written')); return 1 if errs else 0
    if a.cmd == 'suggest':
        rows = suggest(a.ledger, a.min)
        for n, x, y in rows: print(f'{n}\t{x}\t{y}')
        print(f'suggest: {len(rows)} pair(s) changed together at least {a.min} times. A person decides; nothing moved.')
        return 0
    if a.cmd == 'classes':
        n = {}
        for k, val in read_store(a.atoms).items():
            cl = 'secret' if (PLACEHOLDER.match(val) or val.startswith('"@secret(')) else classify(k.split('|')[1], val)
            n[cl] = n.get(cl, 0) + 1
        print(', '.join(f'{v} {k}' for k, v in sorted(n.items()))); return 0


if __name__ == '__main__':
    sys.exit(main())

# Copyright 2026 INPUTLOOP; GPL-3.0-or-later OR LGPL-3.0-or-later.
# Mentat (for Corwin; claude-opus-5-5)
