// SPDX-FileCopyrightText: 2026 INPUTLOOP
// SPDX-License-Identifier: GPL-3.0-or-later OR LGPL-3.0-or-later
//
// atoms-vectors.mjs: the browser's atom layer (site/src/js/omg-atoms.js) against omg_atoms.py's
// own output, byte for byte. For each configuration (the repository's test fixture, the site's
// sample, and edge cases written here) it runs `omg_atoms.py split` and `join` and compares:
// every atom file, the vault, and the joined OBS files. Then atoms -> file -> atoms in JS alone.
//   node site/tests/atoms-vectors.mjs            exit 0 when every vector matches
//   OMG_PROVE_RED=1 node ...                     plants a fault in the JS (a float spelled the JS way);
//                                                the run must then fail
import vm from 'node:vm';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TOP = path.resolve(HERE, '..', '..');
// the module, loaded from its text so a planted fault lands inside it, not on its exports
let SRC = fs.readFileSync(path.join(TOP, 'site', 'src', 'js', 'omg-atoms.js'), 'utf8');
const PY = process.env.PYTHON || 'python3';

if (process.env.OMG_PROVE_RED === '1') {   // spell integral floats the JS way (1, not Python's 1.0)
  const was = SRC;
  SRC = SRC.replace("'0'.repeat(exp + 1 - digits.length) + '.0'", "'0'.repeat(exp + 1 - digits.length)");
  if (SRC === was) { console.log('PLANT FAILED'); process.exit(3); }
}
const mod = { exports: {} };
vm.runInNewContext(SRC, { module: mod, TextDecoder });
const A = mod.exports;

let pass = 0, fail = 0;
const ok = (c, d) => { if (c) pass++; else { fail++; console.log('FAIL ' + d); } };

function walk(dir, base = dir, out = {}) {
  for (const n of fs.readdirSync(dir).sort()) {
    const p = path.join(dir, n);
    if (fs.statSync(p).isDirectory()) walk(p, base, out);
    else out[path.relative(base, p).split(path.sep).join('/')] = fs.readFileSync(p);
  }
  return out;
}
const dec = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });

function vector(name, cfg, { expectMissing = false } = {}) {
  const t = fs.mkdtempSync(path.join(os.tmpdir(), 'omgv-'));
  try {
    execFileSync(PY, [path.join(TOP, 'tools', 'omg_atoms.py'), 'split', cfg, path.join(t, 'atoms'), '--vault', path.join(t, 'vault.kv')], { stdio: 'pipe' });
    const pyStore = walk(path.join(t, 'atoms'));
    const input = {};
    for (const [rel, buf] of Object.entries(walk(cfg))) input[rel] = dec.decode(buf);
    const js = A.split(input);
    const a = Object.keys(pyStore).sort(), b = Object.keys(js.store).sort();
    ok(JSON.stringify(a) === JSON.stringify(b), `${name}: same atom files (py ${a.length}, js ${b.length}; only py: ${a.filter((x) => !b.includes(x)).slice(0, 3)}; only js: ${b.filter((x) => !a.includes(x)).slice(0, 3)})`);
    for (const f of a) if (f in js.store) ok(pyStore[f].equals(Buffer.from(js.store[f], 'utf8')), `${name}: atom file ${f} differs`);
    const pyVault = fs.existsSync(path.join(t, 'vault.kv')) ? A.parseKv(fs.readFileSync(path.join(t, 'vault.kv'), 'utf8')) : [];
    const pv = Object.fromEntries(pyVault.map(([k, v]) => [k, v]));
    ok(JSON.stringify(Object.keys(pv).sort()) === JSON.stringify(Object.keys(js.vault).sort()), `${name}: same vault keys`);
    for (const k of Object.keys(pv)) ok(pv[k] === js.vault[k], `${name}: vault value for ${k}`);
    // join: Python's output, byte for byte
    let pyMissing = '';
    try { execFileSync(PY, [path.join(TOP, 'tools', 'omg_atoms.py'), 'join', path.join(t, 'atoms'), path.join(t, 'out'), '--vault', path.join(t, 'vault.kv')], { stdio: 'pipe' }); }
    catch (e) { pyMissing = String(e.stdout || '') + String(e.stderr || ''); }
    const jj = A.join(js.store, js.vault);
    ok(expectMissing ? jj.missing.length > 0 && pyMissing !== '' : jj.missing.length === 0 && pyMissing === '', `${name}: missing secrets as Python says (js ${jj.missing.length}, py ${pyMissing ? 'some' : 'none'})`);
    for (const k of jj.missing) ok(pyMissing.includes(k), `${name}: Python also misses ${k}`);
    const pyOut = fs.existsSync(path.join(t, 'out')) ? walk(path.join(t, 'out')) : {};
    for (const [rel, buf] of Object.entries(pyOut)) ok(rel in jj.files && buf.equals(Buffer.from(jj.files[rel], 'utf8')), `${name}: joined ${rel} differs from omg_atoms.py's`);
    ok(Object.keys(jj.files).every((r) => r in pyOut), `${name}: no extra joined files`);
    // atoms -> file -> atoms, in the browser's code alone: byte for byte
    if (!expectMissing) {
      const again = A.split(jj.files);
      const s1 = JSON.stringify(Object.entries(js.store).sort()), s2 = JSON.stringify(Object.entries(again.store).sort());
      ok(s1 === s2, `${name}: atoms -> file -> atoms is not byte for byte`);
      // and every INI file is the input, byte for byte
      for (const rel of Object.keys(input)) if (rel.endsWith('.ini')) ok(jj.files[rel] === input[rel], `${name}: ${rel} not byte-exact`);
    }
  } finally { fs.rmSync(t, { recursive: true, force: true }); }
}

function writeTree(root, files) {
  for (const [rel, data] of Object.entries(files)) {
    const p = path.join(root, rel);
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(p, typeof data === 'string' ? Buffer.from(data, 'utf8') : data);
  }
}

const edge = fs.mkdtempSync(path.join(os.tmpdir(), 'omge-'));
const edge2 = fs.mkdtempSync(path.join(os.tmpdir(), 'omgm-'));
try {
  writeTree(edge, {
    // INI: keys before any section, duplicate keys, mixed line endings, no final newline,
    // Python-only whitespace before a comment mark, a BOM-like character mid-file, a lone CR,
    // odd section names, ':' and '%' in keys, Unicode case folding in the secret rule
    'global.ini': 'top=1\n[General]\r\nA=1\nA=2\n\x1c;not a key=1\n\ufeff;a key=2\n\n[a]b]\nv=x\ry\nk:e%y=3\n[Sp ace é]\n\u017Ftream_key=abcdefgh\n\u212Aey=k3lvin00\n# c=1',
    'user.ini': '\ufeff[General]\r\nName=Sample\r\nPassword=\r\nPath=C:\\Users\\you\\x\r\n',
    'basic/profiles/P/basic.ini': '[Output]\nMode=Simple\n[Stream1]\nServer=rtmp://example.invalid/live\nKey=0123456789abcdef\n',
    // JSON: order with number-like keys, a repeated key, Python's float and int spelling,
    // NaN and Infinity, escapes, odd pointer segments, a secret under a key ending in a newline
    'basic/profiles/P/service.json': '\ufeff{"b": 1, "1": 2, "a": {}, "b": 3, "f": [1.0, 0.1, 1e-7, 1e22, 1E5, -0, -0.0, 2.5e+20, 123456789012345678901, 0.30000000000000004, 1e16, 1e15, 100000000000000000000.0], "n": NaN, "i": [Infinity, -Infinity], "s": "\\u0001\\/\\u2028\u00e9\ud83c\udfa5\\t", "a/b": {"~t": {"": null}}, "#x": [[], {}, [[]]], "token\\n": "s3cret-value", "settings": {"key": "live_FAKE_000000000000", "stream_key": ""}}',
    'basic/scenes/S.json': '{"current_scene": "Main", "sources": [{"name": "Caméra 1", "id": "v4l2_input", "settings": {"device_id": "/dev/video0"}}, {"id": "scene"}, {"name": "x/y", "settings": {"monitor": 2, "monitor_id": "\\\\\\\\?\\\\DISPLAY#X"}}], "name": "S", "groups": []}',
    'basic/scenes/T.json': '[1, 2, {"z": true}]',
    'basic/scenes/U.json': '"just text"',
    'basic/scenes/lines.json': '{"a": 1}\n{"b": 2}\n',
    'basic/scenes/old.json.bak': 'ignored',
  });
  writeTree(edge2, { 'global.ini': '[General]\nNote=@secret(len=\u0663)\n' });   // Arabic-Indic three: Python's \d takes it

  vector('repository fixture', path.join(TOP, 'tests', 'fixtures', 'config-small'));
  vector('site sample', path.join(TOP, 'site', 'sample', 'config'));
  vector('edge cases', edge);
  vector('placeholder with a Unicode digit', edge2, { expectMissing: true });

  // the float spelling, on its own, against Python
  const xs = [1, 0.1, 1e-5, 1e-4, 123.456, 1e16, 9999999999999998, 5e-324, 1.7976931348623157e308, -2.5, 0.5e-3, 1234567890123456.7];
  const py = execFileSync(PY, ['-c', 'import sys,json; print("\\n".join(repr(float(x)) for x in sys.argv[1:]))', ...xs.map(String)]).toString().trim().split('\n');
  xs.forEach((x, i) => ok(A.pyFloat(x) === py[i], `float ${x}: js ${A.pyFloat(x)} python ${py[i]}`));
} finally {
  fs.rmSync(edge, { recursive: true, force: true });
  fs.rmSync(edge2, { recursive: true, force: true });
}
console.log(`atoms-vectors: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
