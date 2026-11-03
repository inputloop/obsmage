// @license magnet:?xt=urn:btih:1f739d935676111cfff4b4693e3816e664797050&dn=gpl-3.0.txt GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 INPUTLOOP
// SPDX-License-Identifier: GPL-3.0-or-later OR LGPL-3.0-or-later
//
// omg-compose.js: the screen-map half of tools/omg_compose.py, in the browser. It reads a scene
// collection (as JSON text) and a list of displays, and says what omg_compose.py's `audit`
// says: which display captures bind by index (fragile), which by stable id, which by nothing,
// and which display each one shows. It also gives the geometry of a screen-map scene's items,
// for drawing. It proposes, never applies: `bindPlan` lists the atoms a person may add (the
// stable id beside the index, as the composer does), and the page asks before adding them.
// site/tests/compose-vectors.mjs checks the audit against omg_compose.py's own --json output.
(function (root) {
  'use strict';
  var BIND_KEYS = {
    monitor_capture: ['monitor', 'monitor_id'],
    display_capture: ['display', 'display_uuid'],
    screen_capture: ['display', 'display_uuid'],
    xshm_input: ['screen', null],
    'pipewire-desktop-capture-source': [null, null],
    'pipewire-screen-capture-source': [null, null]
  };
  function has(o, k) { return o && Object.prototype.hasOwnProperty.call(o, k); }
  function get(o, k) { return has(o, k) ? o[k] : null; }
  function fold(s) { return String(s).toLowerCase(); }   // casefold(); the ids here are ASCII

  function classifySource(src) {
    var sid = src && src.id;
    if (!has(BIND_KEYS, sid)) return null;
    var st = src.settings || {};
    if (sid === 'screen_capture' && (has(st, 'type') ? st.type : 0) !== 0) return null;
    var ikey = BIND_KEYS[sid][0], dkey = BIND_KEYS[sid][1];
    var idx = ikey ? get(st, ikey) : null, did = dkey ? get(st, dkey) : null;
    if (did === '') did = null;
    var kind = did !== null ? 'id' : (idx !== null ? 'index' : 'unbound');
    return { name: get(src, 'name'), uuid: get(src, 'uuid'), type: sid, bind: kind, index: idx, id: did, index_key: ikey, id_key: dkey };
  }

  function resolve(rec, displays) {
    var notes = [], byId = null, byIdx = null, i;
    if (rec.id !== null) for (i = 0; i < displays.length; i++) if (displays[i].id && fold(displays[i].id) === fold(rec.id)) { byId = displays[i]; break; }
    if (rec.index !== null) for (i = 0; i < displays.length; i++) if (displays[i].index === rec.index) { byIdx = displays[i]; break; }
    if (rec.bind === 'id') {
      if (!byId) { notes.push('id matches no current display' + (rec.index !== null ? '; OBS would fall back to its index' : '')); return [null, notes]; }
      if (rec.index !== null && (!byIdx || byIdx !== byId)) notes.push('index ' + rec.index + ' now points elsewhere; the id wins');
      return [byId, notes];
    }
    if (rec.bind === 'index') { if (!byIdx) notes.push('index ' + rec.index + ' matches no current display'); return [byIdx, notes]; }
    if (rec.type.indexOf('pipewire') === 0) { notes.push('Wayland portal chooses the display at runtime; cannot be resolved here'); return [null, notes]; }
    var d0 = null; for (i = 0; i < displays.length; i++) if (displays[i].index === 0) { d0 = displays[i]; break; }
    notes.push('no binding set; OBS defaults to monitor index 0');
    return [d0, notes];
  }

  function normalizeDisplays(raw) {
    if (raw && !Array.isArray(raw) && raw.displays) raw = raw.displays;
    return raw.map(function (d, n) {
      return { id: get(d, 'id'), index: get(d, 'index') === null ? n : d.index, name: get(d, 'name'), x: get(d, 'x'), y: get(d, 'y'),
               w: get(d, 'w'), h: get(d, 'h'), primary: get(d, 'primary') === null ? false : d.primary };
    });
  }

  function audit(col, displays) {
    var recs = [], skipped = 0;
    (col.sources || []).forEach(function (s, i) {
      var r = classifySource(s);
      if (!r) { if (s && s.id === 'screen_capture') skipped++; return; }
      r.source_index = i;
      if (displays) {
        var res = resolve(r, displays);
        r.resolves_to = res[0] ? { index: res[0].index, id: res[0].id, name: res[0].name } : null;
        r.notes = res[1];
      }
      recs.push(r);
    });
    var count = function (k) { return recs.filter(function (r) { return r.bind === k; }).length; };
    var out = { sources: recs, summary: { display_capture_sources: recs.length, by_index: count('index'), by_id: count('id'),
                unbound: count('unbound'), skipped_window_or_app_captures: skipped } };
    if (displays) {
      var hit = {};
      recs.forEach(function (r) { if (r.resolves_to) hit[r.resolves_to.index] = 1; });
      out.uncaptured_displays = displays.filter(function (d) { return !hit[d.index]; });
    }
    return out;
  }

  // The items of one scene, placed: x, y, w, h on the canvas (native size from the display the
  // item's capture shows, else the canvas), and which display and binding that is.
  function sceneMap(col, sceneName, displays, canvas) {
    var srcs = col.sources || [], byName = {}, i;
    srcs.forEach(function (s, n) { byName[s.name] = { s: s, n: n }; });
    var sc = byName[sceneName];
    if (!sc || sc.s.id !== 'scene') return null;
    var a = audit(col, displays), recByName = {};
    a.sources.forEach(function (r) { recByName[r.name] = r; });
    var items = ((sc.s.settings || {}).items || []).map(function (it, k) {
      var r = recByName[it.name] || null, disp = null;
      if (r && r.resolves_to) for (i = 0; i < displays.length; i++) if (displays[i].index === r.resolves_to.index) disp = displays[i];
      var w = disp ? disp.w : canvas[0], h = disp ? disp.h : canvas[1];
      var sx = it.scale ? it.scale.x : 1, sy = it.scale ? it.scale.y : 1;
      return { name: it.name, item: k, x: it.pos ? it.pos.x : 0, y: it.pos ? it.pos.y : 0, w: w * sx, h: h * sy,
               visible: it.visible !== false, bind: r ? r.bind : null, display: disp ? disp.name : null };
    });
    return { scene: sceneName, sourceIndex: sc.n, items: items, audit: a };
  }

  // What the composer would add, as atoms: the stable id next to the index it keeps.
  function bindPlan(col, displays) {
    return audit(col, displays).sources.filter(function (r) {
      return r.bind === 'index' && r.id_key && r.resolves_to && r.resolves_to.id;
    }).map(function (r) {
      return { source: r.name, sourceIndex: r.source_index, key: '/sources/#' + r.source_index + '/settings/' + r.id_key,
               value: JSON.stringify(r.resolves_to.id), display: r.resolves_to.name };
    });
  }

  var api = { classifySource: classifySource, resolve: resolve, normalizeDisplays: normalizeDisplays, audit: audit, sceneMap: sceneMap, bindPlan: bindPlan };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.OmgCompose = api;
})(this);
// @license-end
