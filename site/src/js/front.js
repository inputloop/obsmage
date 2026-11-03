// @license magnet:?xt=urn:btih:1f739d935676111cfff4b4693e3816e664797050&dn=gpl-3.0.txt GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 INPUTLOOP
// SPDX-License-Identifier: GPL-3.0-or-later OR LGPL-3.0-or-later
// front.js: when the drawing app in the front page says it is ready (topology forge's
// topoforge:ready message, which ?embed=ready asks for), fit the drawing to its frame once.
// Only a message from that frame, of this site's own origin, is heard. Nothing else is done.
(function () {
  'use strict';
  var f = document.getElementById('topology');
  if (!f) return;
  window.addEventListener('message', function (ev) {
    var m = ev.data;
    if (ev.origin !== window.location.origin || ev.source !== f.contentWindow || !m || m.type !== 'topoforge:ready') return;
    var tf = f.contentWindow && f.contentWindow.TopoForge;
    if (tf && tf.fitView) tf.fitView();
    f.setAttribute('data-ready', '1');
  });
})();
// @license-end
