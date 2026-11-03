// @license magnet:?xt=urn:btih:1f739d935676111cfff4b4693e3816e664797050&dn=gpl-3.0.txt GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 INPUTLOOP
// SPDX-License-Identifier: GPL-3.0-or-later OR LGPL-3.0-or-later
//
// omg-atoms.js: obsmage's atom layer, in the browser. The same format as tools/omg_atoms.py,
// written fresh in JavaScript: an OBS configuration (INI and JSON files) becomes atoms, one
// key and its value per line, one file per set, and joins back. INI comes back byte for byte;
// JSON comes back exactly as omg_atoms.py writes it (4-space indent, keys in its order, numbers
// as Python prints them). A credential becomes @secret(len=N) in the atoms and its value stays
// in a vault object that never leaves the page. Nothing here touches the network.
//
// Where Python and JavaScript differ, this file does what Python does, and says so:
//   - object keys keep their order (JS objects would move "1" before "a"): a small JSON reader
//     of our own keeps them as lists, and a repeated key keeps its first place and last value;
//   - numbers keep Python's spelling: integers exactly (BigInt), floats as Python's repr
//     (1.0, 1e-05, 1e+16), NaN and Infinity as Python's json writes them;
//   - (?i) folds as Python's does (the 'u' flag: the long s and the Kelvin sign fold too);
//     '$' also matches before one final newline; \d is any Unicode digit; lstrip() strips
//     Python's whitespace (which includes \x1c-\x1f and \x85, and not \ufeff);
//   - lengths count code points, not UTF-16 units.
// The test vectors are omg_atoms.py's own output: site/tests/atoms-vectors.mjs runs both.
(function (root) {
  'use strict';

  // ---- classification (omg_atoms.classify) ------------------------------------------------
  var SECRET_KEY = new RegExp('^(token|refreshtoken|refresh_token|access_token|authsecret|authsalt|password|passwd|' +
    'key|stream_?key|secret|.*_secret|.*_token|bearer.*|server_?password|apikey|api_key)\\n?$', 'iu');
  var DEVICE_KEY = new RegExp('^(monitor_id|device_id|video_device_id|audio_device_id|' +
    'monitoringdeviceid|uuid|cookieid|monitor_wgc)\\n?$', 'iu');
  var PATH_VAL = /^([A-Za-z]:\\|\/home\/|\/Users\/|~\/|\\\\)/u;
  var PLACEHOLDER = /^@secret\(len=(\p{Nd}+)\)\n?$/u;
  // Python's str.isspace() set, for str.lstrip()
  var PY_SPACE = /^[\t\n\x0b\x0c\r\x1c-\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/u;

  function cpLen(s) { var n = 0; for (var _ of s) n++; return n; }   // len() in Python: code points
  function rstripSlash(s) { return s.replace(/\/+$/, ''); }
  function lstripHash(s) { return s.replace(/^#+/, ''); }

  function classify(key, value) {
    var parts = rstripSlash(key).split('/');
    var last = lstripHash(parts[parts.length - 1]);
    if (SECRET_KEY.test(last) && ['', '""', 'null', '[]', '{}'].indexOf(value) < 0) return 'secret';
    if (DEVICE_KEY.test(last) || value.startsWith('\\\\?\\') || value.startsWith('"\\\\\\\\?\\\\')) return 'device';
    var v = value.startsWith('"') ? value.slice(1) : value;
    if (PATH_VAL.test(v)) return 'path';
    return 'plain';
  }

  // ---- .kv encoding -------------------------------------------------------------------------
  function encKey(k) { return k.replace(/%/g, '%25').replace(/=/g, '%3D').replace(/\n/g, '%0A').replace(/:/g, '%3A'); }
  function decKey(k) { return k.replace(/%3A/g, ':').replace(/%0A/g, '\n').replace(/%3D/g, '=').replace(/%25/g, '%'); }
  function kvLine(key, value, typed) { return encKey(key) + (typed ? ':=' : '=') + value; }
  function parseKv(text) {
    var out = [];
    text.split('\n').forEach(function (line) {
      if (!line) return;
      var i = line.indexOf('=');
      if (i < 0) throw new Error('not a kv line: ' + JSON.stringify(line));
      var typed = i > 0 && line[i - 1] === ':';
      out.push([decKey(typed ? line.slice(0, i - 1) : line.slice(0, i)), line.slice(i + 1), typed]);
    });
    return out;
  }

  // ---- INI ----------------------------------------------------------------------------------
  function splitIni(text) {
    var bom = text.charCodeAt(0) === 0xfeff;
    if (bom) text = text.slice(1);
    var parts = text.split(/(\r\n|\n)/);
    var lines = [], ends = [];
    for (var i = 0; i < parts.length; i++) (i % 2 ? ends : lines).push(i % 2 ? (parts[i] === '\r\n' ? 'C' : 'N') : parts[i]);
    var crlf = ends.length > 0 && ends.every(function (e) { return e === 'C'; });
    var mixed = ends.indexOf('C') >= 0 && ends.indexOf('N') >= 0;
    var trailing = lines[lines.length - 1] === '';
    if (trailing) lines.pop();
    var shape = [], sets = new Map(), cur = '_head';
    lines.forEach(function (ln) {
      var m = /^\[([^\n]*)\]$/.exec(ln);
      if (m) {
        cur = m[1];
        if (!sets.has(cur)) sets.set(cur, []);
        shape.push('S ' + cur);
      } else if (ln.indexOf('=') >= 0 && !/^[;#]/.test(ln.replace(PY_SPACE, ''))) {
        var j = ln.indexOf('='), k = ln.slice(0, j), v = ln.slice(j + 1);
        if (!sets.has(cur)) sets.set(cur, []);
        sets.get(cur).push([k, v]);
        shape.push('K ' + encKey(k));
      } else {
        shape.push('R ' + ln);
      }
    });
    var meta = { bom: bom, crlf: crlf, trailing: trailing };
    if (mixed) meta.eols = ends.join('');
    return { meta: meta, shape: shape, sets: sets };
  }

  function joinIni(meta, shape, sets) {
    var pos = new Map(), cur = '_head', out = [];
    shape.forEach(function (s) {
      var tag = s[0], rest = s.slice(2);
      if (tag === 'S') { cur = rest; out.push('[' + rest + ']'); }
      else if (tag === 'K') {
        var k = decKey(rest), pk = cur + '\u0000' + k, idx = pos.get(pk) || 0;
        var vals = (sets.get(cur) || []).filter(function (p) { return p[0] === k; }).map(function (p) { return p[1]; });
        if (idx >= vals.length) throw new Error('the shape names ' + k + ' in [' + cur + '] more often than the atoms have it');
        out.push(k + '=' + vals[idx]);
        pos.set(pk, idx + 1);
      } else out.push(rest);
    });
    var text;
    if (meta.eols) {
      var e = meta.eols;
      text = out.map(function (l, i) { return l + (i < e.length ? (e[i] === 'C' ? '\r\n' : '\n') : ''); }).join('');
    } else {
      var nl = meta.crlf ? '\r\n' : '\n';
      text = out.join(nl) + (meta.trailing ? nl : '');
    }
    return (meta.bom ? '\ufeff' : '') + text;
  }

  // ---- JSON, keeping order and Python's spelling ----------------------------------------------
  // Nodes: {t:'o', e:[[key, node], ...]}  {t:'a', v:[node, ...]}  {t:'s', v}  {t:'n', raw}  {t:'b', v}  {t:'z'}
  function parseJson(text) {
    var i = 0, n = text.length;
    function ws() { while (i < n && ' \t\n\r'.indexOf(text[i]) >= 0) i++; }
    function fail(m) { throw new SyntaxError(m + ' at ' + i); }
    function str() {
      i++; var s = '';
      for (;;) {
        if (i >= n) fail('unterminated string');
        var c = text[i];
        if (c === '"') { i++; return s; }
        if (c === '\\') {
          var d = text[i + 1];
          var simple = { '"': '"', '\\': '\\', '/': '/', b: '\b', f: '\f', n: '\n', r: '\r', t: '\t' };
          if (d in simple) { s += simple[d]; i += 2; }
          else if (d === 'u') {
            var h = text.slice(i + 2, i + 6);
            if (!/^[0-9a-fA-F]{4}$/.test(h)) fail('bad \\u escape');
            s += String.fromCharCode(parseInt(h, 16)); i += 6;
          } else fail('bad escape');
        } else if (c.charCodeAt(0) < 0x20) fail('control character in string');   // Python's strict=True
        else { s += c; i++; }
      }
    }
    function value() {
      ws();
      var c = text[i];
      if (c === '{') {
        i++; var e = [], at = new Map(); ws();
        if (text[i] === '}') { i++; return { t: 'o', e: e }; }
        for (;;) {
          ws(); if (text[i] !== '"') fail('expected a key');
          var k = str(); ws(); if (text[i] !== ':') fail('expected :'); i++;
          var v = value();
          if (at.has(k)) e[at.get(k)][1] = v; else { at.set(k, e.length); e.push([k, v]); }   // dict: first place, last value
          ws();
          if (text[i] === ',') { i++; continue; }
          if (text[i] === '}') { i++; return { t: 'o', e: e }; }
          fail('expected , or }');
        }
      }
      if (c === '[') {
        i++; var a = []; ws();
        if (text[i] === ']') { i++; return { t: 'a', v: a }; }
        for (;;) {
          a.push(value()); ws();
          if (text[i] === ',') { i++; continue; }
          if (text[i] === ']') { i++; return { t: 'a', v: a }; }
          fail('expected , or ]');
        }
      }
      if (c === '"') return { t: 's', v: str() };
      var lit = [['true', { t: 'b', v: true }], ['false', { t: 'b', v: false }], ['null', { t: 'z' }],
                 ['NaN', { t: 'n', raw: 'NaN' }], ['Infinity', { t: 'n', raw: 'Infinity' }], ['-Infinity', { t: 'n', raw: '-Infinity' }]];
      for (var L = 0; L < lit.length; L++) if (text.startsWith(lit[L][0], i)) { i += lit[L][0].length; return lit[L][1]; }
      var m = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?/.exec(text.slice(i));
      if (m) { i += m[0].length; return { t: 'n', raw: m[0] }; }
      fail('unexpected character');
    }
    var v = value(); ws();
    if (i !== n) fail('extra data');
    return v;
  }

  // float.__repr__ as Python spells it
  function pyFloat(x) {
    if (Number.isNaN(x)) return 'NaN';
    if (x === Infinity) return 'Infinity';
    if (x === -Infinity) return '-Infinity';
    var neg = x < 0 || Object.is(x, -0), ax = Math.abs(x);
    if (ax === 0) return neg ? '-0.0' : '0.0';
    var ex = ax.toExponential(), p = ex.indexOf('e');   // shortest digits that read back the same
    var digits = ex.slice(0, p).replace('.', ''), exp = parseInt(ex.slice(p + 1), 10), s;
    if (exp >= -4 && exp < 16) {
      if (exp < 0) s = '0.' + '0'.repeat(-exp - 1) + digits;
      else if (digits.length <= exp + 1) s = digits + '0'.repeat(exp + 1 - digits.length) + '.0';
      else s = digits.slice(0, exp + 1) + '.' + digits.slice(exp + 1);
    } else {
      var mant = digits.length > 1 ? digits[0] + '.' + digits.slice(1) : digits;
      var ae = Math.abs(exp);
      s = mant + 'e' + (exp < 0 ? '-' : '+') + (ae < 10 ? '0' : '') + ae;
    }
    return (neg ? '-' : '') + s;
  }
  function numText(raw) {
    if (raw === 'NaN' || raw === 'Infinity' || raw === '-Infinity') return raw;
    if (/[.eE]/.test(raw)) return pyFloat(parseFloat(raw));
    return BigInt(raw).toString();
  }
  // json.dumps(x, ensure_ascii=False) for one node, compact or with indent=4
  function dump(node, indent, level) {
    switch (node.t) {
      case 's': return JSON.stringify(node.v);
      case 'n': return numText(node.raw);
      case 'b': return node.v ? 'true' : 'false';
      case 'z': return 'null';
      case 'a':
        if (!node.v.length) return '[]';
        if (indent === null) return '[' + node.v.map(function (x) { return dump(x, null, 0); }).join(', ') + ']';
        var pa = '\n' + ' '.repeat(indent * (level + 1));
        return '[' + pa + node.v.map(function (x) { return dump(x, indent, level + 1); }).join(',' + pa) + '\n' + ' '.repeat(indent * level) + ']';
      case 'o':
        if (!node.e.length) return '{}';
        if (indent === null) return '{' + node.e.map(function (kv) { return JSON.stringify(kv[0]) + ': ' + dump(kv[1], null, 0); }).join(', ') + '}';
        var po = '\n' + ' '.repeat(indent * (level + 1));
        return '{' + po + node.e.map(function (kv) { return JSON.stringify(kv[0]) + ': ' + dump(kv[1], indent, level + 1); }).join(',' + po) + '\n' + ' '.repeat(indent * level) + '}';
    }
    throw new Error('not a JSON node');
  }
  function dumps(node) { return dump(node, null, 0); }
  function dumpObsJson(node) { return dump(node, 4, 0) + '\n'; }

  function escSeg(s) { s = s.replace(/~/g, '~0').replace(/\//g, '~1'); return s.startsWith('#') ? '~h' + s.slice(1) : s; }
  function unescSeg(s) { if (s.startsWith('~h')) s = '#' + s.slice(2); return s.replace(/~1/g, '/').replace(/~0/g, '~'); }

  function flatten(node, prefix, out) {
    out = out || [];
    prefix = prefix || '';
    if (node.t === 'o' && node.e.length) node.e.forEach(function (kv) { flatten(kv[1], prefix + '/' + escSeg(kv[0]), out); });
    else if (node.t === 'a' && node.v.length) node.v.forEach(function (x, i) { flatten(x, prefix + '/#' + i, out); });
    else out.push([prefix, dumps(node)]);
    return out;
  }

  function unflatten(pairs) {
    var rootNode = null;
    function getKey(o, k) { for (var j = 0; j < o.e.length; j++) if (o.e[j][0] === k) return j; return -1; }
    for (var p = 0; p < pairs.length; p++) {
      var ptr = pairs[p][0], val = parseJson(pairs[p][1]);
      var segs = ptr.split('/').slice(1);
      if (!segs.length) return val;
      if (rootNode === null) rootNode = segs[0].startsWith('#') ? { t: 'a', v: [] } : { t: 'o', e: [] };
      var node = rootNode;
      for (var i = 0; i < segs.length; i++) {
        var seg = segs[i], last = i === segs.length - 1;
        var nxt = last ? null : (segs[i + 1].startsWith('#') ? { t: 'a', v: [] } : { t: 'o', e: [] });
        if (seg.startsWith('#')) {
          var n = parseInt(seg.slice(1), 10);
          if (node.t !== 'a') throw new Error('pointer ' + ptr + ' indexes something that is not a list');
          while (node.v.length <= n) node.v.push({ t: 'z' });
          if (last) node.v[n] = val;
          else { if (node.v[n].t === 'z') node.v[n] = nxt; node = node.v[n]; }
        } else {
          var k = unescSeg(seg);
          if (node.t !== 'o') throw new Error('pointer ' + ptr + ' names a key in something that is not an object');
          var at = getKey(node, k);
          if (last) { if (at >= 0) node.e[at][1] = val; else node.e.push([k, val]); }
          else { if (at < 0) { node.e.push([k, nxt]); at = node.e.length - 1; } node = node.e[at][1]; }
        }
      }
    }
    return rootNode;
  }

  function safe(name) {
    var s = name.replace(/[^A-Za-z0-9._-]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 48);
    return s || 'unnamed';
  }
  function safeSet(s) { return 'set-' + (s !== '_head' ? safe(s) : '_head'); }

  function getField(o, k) { if (o.t !== 'o') return undefined; for (var j = o.e.length - 1; j >= 0; j--) if (o.e[j][0] === k) return o.e[j][1]; return undefined; }

  function jsonSets(obj) {
    var sets = new Map(), src = getField(obj, 'sources');
    if (obj.t === 'o' && src && src.t === 'a') {
      obj.e.forEach(function (kv) {
        if (kv[0] === 'sources') {
          kv[1].v.forEach(function (s, i) {
            var nm = s.t === 'o' ? getField(s, 'name') : undefined;
            if (nm === undefined) nm = { t: 's', v: '' };
            if (nm.t !== 's') throw new TypeError('a source name that is not text (omg_atoms.py stops here too)');
            var sid = 'sources/' + String(i).padStart(3, '0') + '-' + safe(nm.v);
            sets.set(sid, flatten(s, '/sources/#' + i).map(function (p) { return p; }));
          });
        } else {
          if (!sets.has('_top')) sets.set('_top', []);
          Array.prototype.push.apply(sets.get('_top'), flatten(kv[1], '/' + escSeg(kv[0])));
        }
      });
    } else sets.set('_all', flatten(obj));
    return sets;
  }

  // ---- the store: { 'atom file path': text } -------------------------------------------------
  // files: { 'basic/profiles/X/basic.ini': text, ... } (text as UTF-8 decoded, BOM kept as \ufeff)
  function split(files) {
    var store = {}, vault = {}, counts = { plain: 0, path: 0, device: 0, secret: 0 };
    Object.keys(files).filter(function (r) { return /\.(ini|json)$/.test(r) && !/\.bak$/.test(r); }).sort(pyStrCmp).forEach(function (rel) {
      var data = files[rel];
      if (rel.endsWith('.ini')) {
        var r = splitIni(data), order = [];
        store[rel + '/_shape'] = pyMeta(r.meta) + '\n' + r.shape.join('\n') + '\n';
        r.sets.forEach(function (pairs, sname) {
          order.push(sname);
          var lines = pairs.map(function (kv) {
            var k = kv[0], v = kv[1], cls = classify(k, v); counts[cls]++;
            if (cls === 'secret') { vault[rel + '|' + sname + '|' + k] = v; v = '@secret(len=' + cpLen(v) + ')'; }
            return kvLine(k, v, false);
          });
          store[rel + '/' + safeSet(sname) + '.kv'] = lines.join('\n') + '\n';
        });
        store[rel + '/_sets'] = order.join('\n') + '\n';
      } else {
        var obj;
        try { obj = parseJson(data.charCodeAt(0) === 0xfeff ? data.slice(1) : data); }
        catch (e) { store[rel + '/_raw'] = data; return; }
        var sets = jsonSets(obj), names = [];
        sets.forEach(function (pairs, sname) {
          names.push(sname);
          var lines = pairs.map(function (kv) {
            var k = kv[0], v = kv[1], cls = classify(k, v); counts[cls]++;
            if (cls === 'secret') {
              vault[rel + '|' + sname + '|' + k] = v;
              v = JSON.stringify('@secret(len=' + (v.startsWith('"') ? cpLen(parseJson(v).v) : cpLen(v)) + ')');
            }
            return kvLine(k, v, true);
          });
          store[rel + '/' + sname + '.kv'] = lines.join('\n') + '\n';
        });
        store[rel + '/_sets'] = names.join('\n') + '\n';
      }
    });
    return { store: store, vault: vault, counts: counts };
  }
  // json.dumps(meta) as Python writes it: {"bom": false, "crlf": true, "trailing": true[, "eols": "..."]}
  function pyMeta(m) {
    var s = '{"bom": ' + m.bom + ', "crlf": ' + m.crlf + ', "trailing": ' + m.trailing;
    if (m.eols) s += ', "eols": ' + JSON.stringify(m.eols);
    return s + '}';
  }
  // Python sorts str by code point; JS sorts by UTF-16 unit: the same except above U+FFFF.
  function pyStrCmp(a, b) {
    var A = Array.from(a), B = Array.from(b);
    for (var i = 0; i < Math.min(A.length, B.length); i++) { var x = A[i].codePointAt(0), y = B[i].codePointAt(0); if (x !== y) return x - y; }
    return A.length - B.length;
  }

  // -> { files: { rel: text }, missing: [vault keys] }
  function join(store, vault) {
    vault = vault || {};
    var files = {}, missing = [];
    var dirs = {};
    Object.keys(store).forEach(function (p) { var i = p.lastIndexOf('/'); (dirs[p.slice(0, i)] = dirs[p.slice(0, i)] || []).push(p.slice(i + 1)); });
    // sources/NNN-name.kv live one level down: their file is the folder above "sources"
    Object.keys(dirs).sort(pyStrCmp).forEach(function (rel) {
      var names = dirs[rel];
      if (names.indexOf('_raw') >= 0) { files[rel] = store[rel + '/_raw']; return; }
      if (names.indexOf('_sets') < 0) return;
      var order = store[rel + '/_sets'].split('\n').filter(Boolean);
      var mine = [];
      if (rel.endsWith('.ini')) {
        var sh = store[rel + '/_shape'].split('\n');
        var meta = JSON.parse(sh[0]), shape = sh.slice(1).filter(Boolean), sets = new Map();
        order.forEach(function (sname) {
          var pairs = [];
          parseKv(store[rel + '/' + safeSet(sname) + '.kv'] || '').forEach(function (t) {
            var k = t[0], v = t[1];
            if (PLACEHOLDER.test(v)) {
              var key = rel + '|' + sname + '|' + k;
              if (!(key in vault)) { mine.push(key); return; }
              v = vault[key];
            }
            pairs.push([k, v]);
          });
          sets.set(sname, pairs);
        });
        if (!mine.length) files[rel] = joinIni(meta, shape, sets);
      } else {
        var all = [];
        order.forEach(function (sname) {
          parseKv(store[rel + '/' + sname + '.kv'] || '').forEach(function (t) {
            var k = t[0], v = t[1];
            if (v.startsWith('"@secret(len=')) {
              var key = rel + '|' + sname + '|' + k;
              if (!(key in vault)) { mine.push(key); return; }
              v = vault[key];
            }
            all.push([k, v]);
          });
        });
        if (!mine.length) files[rel] = dumpObsJson(unflatten(all));
      }
      Array.prototype.push.apply(missing, mine);
    });
    return { files: files, missing: missing };
  }

  var api = {
    classify: classify, encKey: encKey, decKey: decKey, kvLine: kvLine, parseKv: parseKv,
    splitIni: splitIni, joinIni: joinIni, parseJson: parseJson, dumps: dumps, dumpObsJson: dumpObsJson,
    pyFloat: pyFloat, flatten: flatten, unflatten: unflatten, safe: safe, safeSet: safeSet,
    split: split, join: join, cpLen: cpLen, PLACEHOLDER: PLACEHOLDER
  };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.OmgAtoms = api;
})(this);
// @license-end
