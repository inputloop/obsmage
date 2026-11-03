// @license magnet:?xt=urn:btih:1f739d935676111cfff4b4693e3816e664797050&dn=gpl-3.0.txt GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 INPUTLOOP
// SPDX-License-Identifier: GPL-3.0-or-later OR LGPL-3.0-or-later
// look.js: before the page is drawn, apply the theme this browser chose (light, dark, or the
// system's), and mark the page as scripted. Keeps one value, obsmage.theme; storage refused is fine.
(function () {
  'use strict';
  var d = document.documentElement, t = null;
  d.classList.add('js');
  try { t = window.localStorage.getItem('obsmage.theme'); } catch (e) { /* storage off: the system decides */ }
  if (t === 'light' || t === 'dark') d.setAttribute('data-theme', t);
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest && ev.target.closest('[data-theme-set]');
    if (!b) return;
    var v = b.getAttribute('data-theme-set');
    if (v === 'auto') d.removeAttribute('data-theme'); else d.setAttribute('data-theme', v);
    try { if (v === 'auto') window.localStorage.removeItem('obsmage.theme'); else window.localStorage.setItem('obsmage.theme', v); } catch (e) { /* not kept */ }
    mark();
  });
  function mark() {
    var cur = d.getAttribute('data-theme') || 'auto';
    Array.prototype.forEach.call(document.querySelectorAll('[data-theme-set]'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-theme-set') === cur)); });
  }
  document.addEventListener('DOMContentLoaded', mark);
})();
// @license-end
