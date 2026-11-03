// SPDX-FileCopyrightText: 2026 INPUTLOOP
// SPDX-License-Identifier: GPL-3.0-or-later OR LGPL-3.0-or-later
//
// compose-vectors.mjs: the browser's audit (site/src/js/omg-compose.js) against omg_compose.py
// audit --json, on the repository's fixtures and the site's sample. OMG_PROVE_RED=1 plants a
// fault (unbound captures counted as bound by index); the run must then fail.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const TOP = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
import vm from 'node:vm';
// the module, loaded from its text so a planted fault lands inside it, not on its exports
let SRC = fs.readFileSync(path.join(TOP, 'site/src/js/omg-compose.js'), 'utf8');
if (process.env.OMG_PROVE_RED === '1') {
  const was = SRC;
  SRC = SRC.replace(": (idx !== null ? 'index' : 'unbound')", ": 'index'");
  if (SRC === was) { console.log('PLANT FAILED'); process.exit(3); }
}
const mod = { exports: {} };
vm.runInNewContext(SRC, { module: mod });
const C = mod.exports;
let pass = 0, fail = 0;
const ok = (c, d) => { if (c) pass++; else { fail++; console.log('FAIL ' + d); } };
const pairs = [
  ['tests/fixtures/three-heads.json', 'tests/fixtures/displays-four.json'],
  ['site/sample/config/basic/scenes/Sample_Desk.json', 'site/sample/displays.json'],
];
for (const [col, disp] of pairs) {
  const py = JSON.parse(execFileSync('python3', [path.join(TOP, 'tools/omg_compose.py'), 'audit', path.join(TOP, col), '--displays', path.join(TOP, disp), '--json']).toString());
  const js = C.audit(JSON.parse(fs.readFileSync(path.join(TOP, col), 'utf8')), C.normalizeDisplays(JSON.parse(fs.readFileSync(path.join(TOP, disp), 'utf8'))));
  js.sources.forEach((r) => delete r.source_index);
  ok(JSON.stringify(js.summary) === JSON.stringify(py.summary), `${col}: summary js ${JSON.stringify(js.summary)} py ${JSON.stringify(py.summary)}`);
  ok(JSON.stringify(js.sources) === JSON.stringify(py.sources), `${col}: per-source records differ`);
  ok(JSON.stringify(js.uncaptured_displays) === JSON.stringify(py.uncaptured_displays), `${col}: uncaptured displays differ`);
}
console.log(`compose-vectors: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
