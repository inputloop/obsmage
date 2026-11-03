// @license magnet:?xt=urn:btih:1f739d935676111cfff4b4693e3816e664797050&dn=gpl-3.0.txt GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 INPUTLOOP
// SPDX-License-Identifier: GPL-3.0-or-later OR LGPL-3.0-or-later
//
// demo.js: the obsmage demo. An OBS setup (the invented sample, or files the visitor chooses)
// is split into atoms with omg-atoms.js; every edit to an atom joins the OBS files again, and the
// joined files are split once more and compared with the atoms, byte for byte, and the result is
// said. The screen map is drawn from the scene collection with omg-compose.js; dragging a screen
// (or the arrow keys) writes its position atoms. Nothing is sent anywhere: this page's policy
// gives it no connection at all, and nothing is kept after the tab closes.
(function () {
  'use strict';
  var A = window.OmgAtoms, C = window.OmgCompose;
  var $ = function (id) { return document.getElementById(id); };
  if (!A || !C || !$('demo')) return;

  var S = { files: null, store: null, vault: null, displays: null, set: null, file: null, shown: {}, mine: false };
  var SAMPLE = JSON.parse($('sample').textContent);
  var rt = $('rt');

  function el(tag, attrs, kids) {
    var n = /^(svg|rect|text|g|line|title|tspan)$/.test(tag) ? document.createElementNS('http://www.w3.org/2000/svg', tag) : document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function say(text, cls) { rt.textContent = text; rt.className = 'status' + (cls ? ' ' + cls : ''); }

  // ---- the store ---------------------------------------------------------------------------
  function fileDirs() {
    return Object.keys(S.store).filter(function (p) { return /\/_sets$/.test(p); }).map(function (p) { return p.slice(0, -6); }).sort();
  }
  function setsOf(rel) {
    return S.store[rel + '/_sets'].split('\n').filter(Boolean).map(function (s) {
      return { name: s, path: rel + '/' + (rel.endsWith('.ini') ? A.safeSet(s) : s) + '.kv', ini: rel.endsWith('.ini') };
    });
  }
  function isWithheld(v, typed) { return typed ? v.indexOf('"@secret(len=') === 0 : A.PLACEHOLDER.test(v); }
  function counts() {
    var n = 0, w = 0;
    Object.keys(S.store).forEach(function (p) {
      if (!/\.kv$/.test(p)) return;
      A.parseKv(S.store[p]).forEach(function (t) { n++; if (isWithheld(t[1], t[2])) w++; });
    });
    return { atoms: n, withheld: w };
  }

  function load(files, displays, mine) {
    var r = A.split(files);
    S.store = r.store; S.vault = r.vault; S.displays = displays; S.mine = !!mine; S.shown = {};
    S.files = null;
    var dirs = fileDirs();
    if (!dirs.length) { say('Nothing to split: none of those looked like an OBS .ini or .json file.', 'bad'); return false; }
    fillPickers();
    rejoin(null);
    return true;
  }

  function fillPickers() {
    var sp = $('set-pick'); clear(sp);
    fileDirs().forEach(function (rel) {
      var g = el('optgroup', { label: rel });
      setsOf(rel).forEach(function (s) { g.appendChild(el('option', { value: s.path }, [s.ini ? '[' + s.name + ']' : s.name.replace(/^sources\/\d+-/, 'source: ')])); });
      sp.appendChild(g);
    });
    var want = Object.keys(S.store).filter(function (p) { return /Screenmap\.kv$/.test(p); })[0] || sp.options[0].value;
    sp.value = want; S.set = want;
    var fp = $('file-pick'); clear(fp);
    fileDirs().forEach(function (rel) { fp.appendChild(el('option', { value: rel }, [rel])); });
    S.file = S.set.replace(/\/(sources\/)?[^/]+\.kv$/, '');
    fp.value = S.file;
  }

  // ---- atoms -------------------------------------------------------------------------------
  function renderAtoms(hits) {
    var list = $('atom-list'); clear(list);
    var rel = S.set.replace(/\/(sources\/)?[^/]+\.kv$/, ''), typedFile = !rel.endsWith('.ini');
    var sname = setsOf(rel).filter(function (s) { return s.path === S.set; })[0];
    $('set-what').textContent = (typedFile ? 'Typed atoms (key:=JSON) from ' : 'Atoms (key=value) from ') + rel +
      (sname ? (typedFile ? ', set ' + sname.name : ', section [' + sname.name + ']') : '') + '. Each line is one atom; change a value and the file is joined again.';
    var rows = A.parseKv(S.store[S.set] || '');
    rows.forEach(function (t, i) {
      var k = t[0], v = t[1], typed = t[2], held = isWithheld(v, typed);
      var cls = held ? 'secret' : A.classify(k, v);
      var id = 'atom-' + i;
      var input = el('input', { id: id, type: 'text', value: v, spellcheck: 'false', autocomplete: 'off', 'data-i': String(i) });
      if (held) { input.readOnly = true; input.setAttribute('aria-describedby', id + '-c'); }
      var row = el('div', { class: 'atom' + (hits && hits.indexOf(k) >= 0 ? ' hit' : '') }, [
        el('label', { for: id }, [k + (typed ? ' :=' : ' =')]), input,
        el('span', { class: 'cls cls-' + cls, id: id + '-c' }, [held ? 'secret: withheld, its value is in this tab\'s vault only' : cls]),
        el('span', { class: 'err', id: id + '-e', role: 'alert' })
      ]);
      list.appendChild(row);
      if (!held) {
        input.addEventListener('input', function () { edit(i, input, typed); });
        input.addEventListener('change', function () { tidy(i, input, typed); });
      }
    });
    if (hits) { var h = list.querySelector('.hit'); if (h) list.scrollTop = Math.max(0, h.offsetTop - list.offsetTop - 8); }   // the list scrolls, never the page
  }

  function writeAtom(path, i, value) {
    var rows = A.parseKv(S.store[path]);
    rows[i][1] = value;
    S.store[path] = rows.map(function (t) { return A.kvLine(t[0], t[1], t[2]); }).join('\n') + '\n';
  }
  function canon(v) { return A.dumps(A.parseJson(v)); }   // as omg_atoms.py would write it
  function edit(i, input, typed) {
    var err = $(input.id + '-e'), v = input.value;
    if (typed) {
      try { v = canon(v); } catch (e) {
        input.setAttribute('aria-invalid', 'true');
        err.textContent = 'Not JSON yet (a string needs its quotes): the file keeps the last good value.';
        return;
      }
    }
    input.removeAttribute('aria-invalid'); err.textContent = '';
    writeAtom(S.set, i, v);
    rejoin(S.set.replace(/\/(sources\/)?[^/]+\.kv$/, ''));
  }
  function tidy(i, input, typed) {
    if (!typed || input.getAttribute('aria-invalid')) return;
    var c = A.parseKv(S.store[S.set])[i][1];
    if (c !== input.value) { $(input.id + '-e').textContent = 'Written as ' + c + ', the way obsmage writes it.'; input.value = c; }
  }

  // ---- join, and the round trip ---------------------------------------------------------------
  function rejoin(focusFile) {
    var j = A.join(S.store, S.vault);
    if (j.missing.length) { say('Cannot join: ' + j.missing.length + ' withheld value(s) are not in the vault.', 'bad'); return; }
    var before = S.files || {};
    S.files = j.files;
    var again = A.split(S.files), same = true, where = '';
    var a = Object.keys(S.store).sort(), b = Object.keys(again.store).sort();
    if (a.join('\n') !== b.join('\n')) { same = false; where = 'the list of atom files'; }
    else for (var k = 0; k < a.length; k++) if (S.store[a[k]] !== again.store[a[k]]) { same = false; where = a[k]; break; }
    var c = counts();
    if (same) say('atoms \u2192 OBS files \u2192 atoms: identical, byte for byte. ' + c.atoms + ' atoms in ' + Object.keys(S.files).length +
                  ' files; ' + c.withheld + ' withheld.' + (S.mine ? ' Your files have not left this page.' : ''), 'ok');
    else say('atoms \u2192 OBS files \u2192 atoms differs at ' + where + '. This is a fault in the demo; please tell us.', 'bad');
    if (focusFile && focusFile !== S.file) { S.file = focusFile; $('file-pick').value = focusFile; }
    renderFile(before[S.file]);
    renderMap();
  }

  // ---- the file -----------------------------------------------------------------------------
  function masks(rel) {
    var out = [];
    Object.keys(S.vault).forEach(function (k) {
      if (k.indexOf(rel + '|') !== 0) return;
      var v = S.vault[k];
      if (v.charAt(0) === '"') { try { v = JSON.stringify(A.parseJson(v).v).slice(1, -1); } catch (e) { /* keep raw */ } }
      if (v) out.push(v);
    });
    return out.sort(function (x, y) { return y.length - x.length; });
  }
  function renderFile(old) {
    var pre = $('file-view'); clear(pre);
    var text = S.files[S.file];
    if (text === undefined) { pre.textContent = 'This file could not be joined.'; return; }
    var lines = text.replace(/^\ufeff/, '').split(/\r?\n/), seen = {};
    if (old !== undefined) old.replace(/^\ufeff/, '').split(/\r?\n/).forEach(function (l) { seen[l] = (seen[l] || 0) + 1; });
    var hide = $('reveal').checked ? [] : masks(S.file), first = null;
    lines.forEach(function (l, i) {
      if (i === lines.length - 1 && l === '') return;
      var changed = old !== undefined && !(seen[l] > 0);
      if (seen[l] > 0) seen[l]--;
      var span = el('span', { class: 'ln' + (changed ? ' changed' : '') });
      var rest = l, done = false;
      while (!done) {
        var at = -1, m = null;
        hide.forEach(function (h) { var p = rest.indexOf(h); if (p >= 0 && (at < 0 || p < at)) { at = p; m = h; } });
        if (at < 0) { span.appendChild(document.createTextNode(rest)); done = true; }
        else {
          span.appendChild(document.createTextNode(rest.slice(0, at)));
          span.appendChild(el('span', { class: 'withheld', title: 'withheld' }, ['\u2022\u2022\u2022\u2022 withheld, ' + A.cpLen(m) + ' characters \u2022\u2022\u2022\u2022']));
          rest = rest.slice(at + m.length);
        }
      }
      pre.appendChild(span);
      if (changed && !first) first = span;
    });
    var facts = $('file-facts');
    if (!facts) { facts = el('p', { id: 'file-facts', class: 'hint' }); pre.parentNode.insertBefore(facts, pre.nextSibling); }
    var bom = text.charCodeAt(0) === 0xfeff, crlf = /\r\n/.test(text), lf = /(^|[^\r])\n/.test(text);
    facts.textContent = S.file + ': UTF-8' + (bom ? ' with a byte-order mark' : '') + ', ' + (crlf && lf ? 'mixed line endings' : crlf ? 'CRLF line endings' : 'LF line endings') +
      ', ' + text.length + ' characters' + (S.file.endsWith('.ini') ? '; joined byte for byte.' : '; joined the way OBS reads JSON.');
    if (first) pre.scrollTop = Math.max(0, first.offsetTop - pre.offsetTop - 3 * 21);   // the file scrolls, never the page
  }

  // ---- the screen map -------------------------------------------------------------------------
  function collection() {
    var names = Object.keys(S.files).filter(function (r) { return /^basic\/scenes\/[^/]+\.json$/.test(r); });
    for (var i = 0; i < names.length; i++) {
      var col; try { col = JSON.parse(S.files[names[i]]); } catch (e) { continue; }
      var scenes = (col.sources || []).filter(function (s) { return s.id === 'scene'; });
      var pick = scenes.filter(function (s) { return /screen ?map/i.test(s.name); })[0] || scenes.filter(function (s) {
        return ((s.settings || {}).items || []).some(function (it) { return (col.sources || []).some(function (x) { return x.name === it.name && C.classifySource(x); }); });
      })[0];
      if (pick) return { rel: names[i], col: col, scene: pick.name };
    }
    return null;
  }
  function canvasSize() {
    var p = Object.keys(S.store).filter(function (k) { return /basic\.ini\/set-Video\.kv$/.test(k); })[0], w = 1920, h = 1080;
    if (p) A.parseKv(S.store[p]).forEach(function (t) { if (t[0] === 'BaseCX') w = +t[1] || w; if (t[0] === 'BaseCY') h = +t[1] || h; });
    return [w, h];
  }
  function bindWords(r) {
    if (!r) return 'not a screen capture';
    var shows = r.resolves_to ? ' It shows ' + (r.resolves_to.name || 'a screen') + '.' : (S.displays ? ' It shows no current screen.' : '');
    if (r.bind === 'id') return '"' + r.name + '" is bound by the screen\'s own id, which follows the screen.' + shows;
    if (r.bind === 'index') return '"' + r.name + '" is bound by position number ' + r.index + ', which points elsewhere when a screen is unplugged.' + shows;
    return '"' + r.name + '" is bound to nothing, so OBS uses position number 0.' + shows;
  }

  function renderMap() {
    var desk = $('desk'), scene = $('scene'), au = $('audit');
    [desk, scene].forEach(function (s) { Array.prototype.slice.call(s.childNodes).forEach(function (n) { if (n.nodeName !== 'title') s.removeChild(n); }); });
    clear(au);
    var found = collection();
    if (!found) { au.appendChild(el('li', { class: 'b-note' }, ['No scene with screen captures in these files, so there is no screen map to draw.'])); $('bind').hidden = true; return; }
    $('bind').hidden = !S.displays;
    var cv = canvasSize(), disp = S.displays ? C.normalizeDisplays(S.displays) : [];
    var map = C.sceneMap(found.col, found.scene, disp, cv);
    S.map = { found: found, map: map, canvas: cv, disp: disp };
    // the desk
    if (disp.length) {
      var x0 = Math.min.apply(null, disp.map(function (d) { return d.x; })), y0 = Math.min.apply(null, disp.map(function (d) { return d.y; }));
      var x1 = Math.max.apply(null, disp.map(function (d) { return d.x + d.w; })), y1 = Math.max.apply(null, disp.map(function (d) { return d.y + d.h; }));
      var pad = 160;
      desk.setAttribute('viewBox', [x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad].join(' '));
      disp.forEach(function (d) {
        desk.appendChild(el('rect', { class: 'disp', x: d.x + 20, y: d.y + 20, width: d.w - 40, height: d.h - 40 }));
        desk.appendChild(el('text', { class: 'disp-t', x: d.x + 90, y: d.y + 340, 'font-size': 300 }, [d.name || ('#' + d.index)]));
        desk.appendChild(el('text', { class: 'disp-s', x: d.x + 90, y: d.y + 560, 'font-size': 190 }, ['#' + d.index + ' \u00b7 ' + d.w + '\u00d7' + d.h]));
      });
    } else {
      desk.setAttribute('viewBox', '0 0 1600 900');
      desk.appendChild(el('text', { class: 'disp-s', x: 80, y: 420, 'font-size': 64 }, ['These files do not say where the screens sit;']));
      desk.appendChild(el('text', { class: 'disp-s', x: 80, y: 520, 'font-size': 64 }, ['omg_compose.py displays reads that from the machine.']));
    }
    // the scene
    scene.setAttribute('viewBox', '0 0 ' + cv[0] + ' ' + cv[1]);
    scene.appendChild(el('rect', { class: 'canvas', x: 0, y: 0, width: cv[0], height: cv[1] }));
    map.items.forEach(function (it) {
      var b = it.bind || 'none';
      var label = it.name + ': ' + (b === 'id' ? 'bound by id' : b === 'index' ? 'bound by position number' : b === 'unbound' ? 'bound to nothing' : 'not a screen capture') +
        (it.visible ? '' : ', hidden') + ', at ' + Math.round(it.x) + ', ' + Math.round(it.y) + '. Arrow keys move it.';
      var g = el('g', { class: 'scene-item b-' + b, tabindex: '0', role: 'button', 'aria-label': label, 'data-item': String(it.item) }, [
        el('rect', { x: it.x, y: it.y, width: Math.max(it.w, 8), height: Math.max(it.h, 8) }),
        el('text', { class: 'item-t', x: it.x + 14, y: it.y + 60, 'font-size': 54 }, [it.name + (it.visible ? '' : ' (hidden)')]),
        el('text', { class: 'item-s', x: it.x + 14, y: it.y + 112, 'font-size': 42 }, [b === 'id' ? 'by id' : b === 'index' ? 'by position' : b === 'unbound' ? 'unbound' : ''])
      ]);
      if (!it.visible) g.setAttribute('opacity', '0.45');
      scene.appendChild(g);
      drag(g, it);
    });
    // the audit, in words
    map.audit.sources.forEach(function (r) { au.appendChild(el('li', { class: 'b-' + r.bind }, [bindWords(r)])); });
    (map.audit.uncaptured_displays || []).forEach(function (d) { au.appendChild(el('li', { class: 'b-note' }, ['No capture shows ' + (d.name || 'screen #' + d.index) + '.'])); });
  }

  function itemPath(itemIndex) {
    var f = S.map.found, srcIdx = map_sourceIndex();
    var pref = '/sources/#' + srcIdx + '/settings/items/#' + itemIndex + '/pos/';
    var sets = setsOf(f.rel), path = null;
    sets.forEach(function (s) { if (A.parseKv(S.store[s.path]).some(function (t) { return t[0].indexOf(pref) === 0; })) path = s.path; });
    return { path: path, x: pref + 'x', y: pref + 'y' };
  }
  function map_sourceIndex() { return S.map.map.sourceIndex; }
  function setPos(itemIndex, x, y) {
    var p = itemPath(itemIndex);
    if (!p.path) { say('This item has no position atoms to write.', 'bad'); return; }
    var rows = A.parseKv(S.store[p.path]);
    rows.forEach(function (t) {
      if (t[0] === p.x) t[1] = A.dumps({ t: 'n', raw: (Math.round(x * 10) / 10).toFixed(1) });
      if (t[0] === p.y) t[1] = A.dumps({ t: 'n', raw: (Math.round(y * 10) / 10).toFixed(1) });
    });
    S.store[p.path] = rows.map(function (t) { return A.kvLine(t[0], t[1], t[2]); }).join('\n') + '\n';
    S.set = p.path; $('set-pick').value = p.path;
    renderAtoms([p.x, p.y]);
    rejoin(S.map.found.rel);
    var g = $('scene').querySelector('[data-item="' + itemIndex + '"]');
    if (g) g.focus();
  }
  function drag(g, it) {
    var svg = $('scene'), start = null;
    function pt(ev) { var p = svg.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY; return p.matrixTransform(svg.getScreenCTM().inverse()); }
    g.addEventListener('pointerdown', function (ev) {
      var p = pt(ev); start = { dx: p.x - it.x, dy: p.y - it.y, x: it.x, y: it.y };
      g.setPointerCapture(ev.pointerId); g.classList.add('dragging'); ev.preventDefault();
    });
    g.addEventListener('pointermove', function (ev) {
      if (!start) return;
      var p = pt(ev); start.x = p.x - start.dx; start.y = p.y - start.dy;
      g.setAttribute('transform', 'translate(' + (start.x - it.x) + ' ' + (start.y - it.y) + ')');
    });
    function end() { if (!start) return; var s = start; start = null; g.classList.remove('dragging'); if (s.x !== it.x || s.y !== it.y) setPos(it.item, s.x, s.y); }
    g.addEventListener('pointerup', end);
    g.addEventListener('pointercancel', function () { start = null; g.removeAttribute('transform'); g.classList.remove('dragging'); });
    g.addEventListener('keydown', function (ev) {
      var step = ev.shiftKey ? 40 : 4, d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[ev.key];
      if (!d) return;
      ev.preventDefault();
      setPos(it.item, it.x + d[0], it.y + d[1]);
    });
  }

  // ---- the composer's proposal ------------------------------------------------------------------
  $('bind').addEventListener('click', function () {
    var box = $('plan'); clear(box); box.hidden = false;
    var f = S.map.found, plan = C.bindPlan(f.col, S.map.disp);
    var loose = S.map.map.audit.sources.filter(function (r) { return r.bind === 'unbound'; });
    if (!plan.length) box.appendChild(el('p', {}, ['Nothing to propose: no capture is bound by position number to a screen that has an id.']));
    else {
      box.appendChild(el('p', {}, ['The composer would add ' + plan.length + ' atom' + (plan.length > 1 ? 's' : '') + ', keeping each position number for older OBS:']));
      box.appendChild(el('pre', {}, [plan.map(function (p) { return A.kvLine(p.key, p.value, true); }).join('\n')]));
      var add = el('button', { type: 'button' }, ['Add ' + (plan.length > 1 ? 'these atoms' : 'this atom')]);
      var no = el('button', { type: 'button' }, ['Not now']);
      box.appendChild(el('div', { class: 'row' }, [add, no]));
      add.addEventListener('click', function () {
        var target = null;
        plan.forEach(function (p) {
          var s = setsOf(f.rel).filter(function (x) { return x.name.indexOf('sources/' + String(p.sourceIndex).padStart(3, '0') + '-') === 0; })[0];
          if (!s) return;
          insertAtom(s.path, p.key, p.value);
          target = target || s.path;
        });
        box.hidden = true;
        if (target) { S.set = target; $('set-pick').value = target; renderAtoms(plan.map(function (p) { return p.key; })); }
        rejoin(f.rel);
      });
      no.addEventListener('click', function () { box.hidden = true; });
    }
    loose.forEach(function (r) { box.appendChild(el('p', { class: 'hint' }, ['"' + r.name + '" is bound to nothing. Which screen it should show is a person\'s call; omg_compose.py compose can add a capture for any screen none shows.'])); });
  });

  // A new atom goes where joining puts it: after the last atom under the same parent (so the
  // atoms read in the file's own order, and atoms -> file -> atoms stays byte for byte). A
  // parent that was an empty {} leaf is replaced by the new key.
  function insertAtom(path, key, value) {
    var rows = A.parseKv(S.store[path]), parent = key.slice(0, key.lastIndexOf('/')), at = -1;
    rows = rows.filter(function (t) { return !(t[0] === parent && t[1] === '{}'); });
    rows.forEach(function (t, i) { if (t[0].indexOf(parent + '/') === 0) at = i; });
    rows.splice(at < 0 ? rows.length : at + 1, 0, [key, value, true]);
    S.store[path] = rows.map(function (t) { return A.kvLine(t[0], t[1], t[2]); }).join('\n') + '\n';
  }

  // ---- pickers and your own files ---------------------------------------------------------------
  $('set-pick').addEventListener('change', function () { S.set = this.value; renderAtoms(); var rel = S.set.replace(/\/(sources\/)?[^/]+\.kv$/, ''); if (rel !== S.file) { S.file = rel; $('file-pick').value = rel; renderFile(); } });
  $('file-pick').addEventListener('change', function () { S.file = this.value; renderFile(); });
  $('reveal').addEventListener('change', function () { renderFile(); });

  function placeOf(name) {
    var n = name.replace(/^.*[\\/]/, '');
    if (/^(global|user)\.ini$/i.test(n)) return n.toLowerCase();
    if (/^basic\.ini$/i.test(n)) return 'basic/profiles/Mine/basic.ini';
    if (/^(service|streamEncoder|recordEncoder)\.json$/i.test(n)) return 'basic/profiles/Mine/' + n;
    if (/\.json$/i.test(n)) return 'basic/scenes/' + n.replace(/[^A-Za-z0-9 ._-]/g, '_');
    if (/\.ini$/i.test(n)) return n.replace(/[^A-Za-z0-9 ._-]/g, '_');
    return null;
  }
  var dec = new TextDecoder('utf-8', { ignoreBOM: true });
  function own(files) {
    if (load(files, null, true)) {
      var c = counts();
      $('own-say').textContent = 'Split here: ' + c.atoms + ' atoms, ' + c.withheld + ' credential' + (c.withheld === 1 ? '' : 's') + ' withheld. Nothing was sent; close the tab and it is gone.';
      renderAtoms();
    }
  }
  $('own-go').addEventListener('click', function () {
    var picked = $('own-files').files, text = $('own-text').value, files = {}, waiting = 0, skipped = [];
    if (text.trim()) files[$('own-kind').value] = text;
    Array.prototype.forEach.call(picked || [], function (f) {
      var rel = placeOf(f.name);
      if (!rel || f.size > 8 * 1024 * 1024) { skipped.push(f.name); return; }
      waiting++;
      f.arrayBuffer().then(function (buf) { files[rel] = dec.decode(buf); }).catch(function () { skipped.push(f.name); }).then(function () { if (--waiting === 0) finish(); });
    });
    function finish() {
      if (skipped.length) $('own-say').textContent = 'Left out (not an OBS .ini or .json, or over 8 MB): ' + skipped.join(', ');
      if (Object.keys(files).length) { try { own(files); } catch (e) { $('own-say').textContent = 'Could not split these: ' + e.message; } }
      else if (!skipped.length) $('own-say').textContent = 'Choose a file or paste one first.';
    }
    if (!waiting) finish();
  });
  $('sample-go').addEventListener('click', function () { $('own-say').textContent = ''; start(); });

  // the sample opens on the Screenmap scene's first screen, its position atoms marked: drag it and watch them
  function start() { if (load(SAMPLE.files, SAMPLE.displays, false)) renderAtoms(S.map ? ['x', 'y'].map(function (k) { return '/sources/#' + S.map.map.sourceIndex + '/settings/items/#0/pos/' + k; }) : null); }
  start();
  window.obsmageDemo = { state: S, roundTrip: function () { var j = A.join(S.store, S.vault), again = A.split(j.files); return JSON.stringify(Object.entries(again.store).sort()) === JSON.stringify(Object.entries(S.store).sort()); } };
})();
// @license-end
