// SPDX-FileCopyrightText: 2026 INPUTLOOP
// SPDX-License-Identifier: GPL-3.0-or-later OR LGPL-3.0-or-later
//
// browser.cjs: obsmage.com in Chromium, served under the deploy policies (read from
// site/deploy/*.conf and site/generated/topology-csp.conf, so the test serves what nginx will).
//   SITE_OUT=dir SHOTS=dir node site/tests/browser.cjs
// At 390, 1280 and 1920 wide, light and dark: no console error, no request to another host,
// no sideways scroll, text contrast at WCAG 2.1 AA. The demo: atoms -> file -> atoms byte for
// byte, an edit shows in the file, withheld values stay withheld, a screen moves by drag and by
// keys, the composer's proposal adds its atoms, pasted files are split here. Scripts off too.
const http = require('node:http'), fs = require('node:fs'), path = require('node:path');
const { chromium } = require('playwright');

const SITE = path.resolve(__dirname, '..');
const OUT = process.env.SITE_OUT || path.join(SITE, 'public');
const GEN = process.env.SITE_GEN || path.join(SITE, 'generated');
const SHOTS = process.env.SHOTS || '';
const conf = fs.readFileSync(path.join(SITE, 'deploy', 'nginx-obsmage.com.conf'), 'utf8');
const SITE_POLICY = /location \/ \{[^}]*Content-Security-Policy "([^"]+)"/.exec(conf)[1];
const tp = fs.readFileSync(path.join(GEN, 'topology-csp.conf'), 'utf8');
const TOPO_POLICY = (/"([^"]+)"/.exec(tp) || [, SITE_POLICY])[1];
const TYPES = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.woff': 'font/woff', '.woff2': 'font/woff2', '.txt': 'text/plain; charset=utf-8', '.png': 'image/png', '.org': 'text/plain; charset=utf-8', '.md': 'text/plain; charset=utf-8' };

let fails = 0, passes = 0;
const ok = (c, d) => { if (c) passes++; else { fails++; console.log('FAIL ' + d); } };

const server = http.createServer((req, res) => {
  let u = decodeURIComponent(req.url.split('?')[0]);
  if (u.endsWith('/')) u += 'index.html';
  const file = path.join(OUT, path.normalize(u).replace(/^(\.\.[/\\])+/, ''));
  const pol = u.startsWith('/topology/') ? TOPO_POLICY : SITE_POLICY;
  const h = { 'Content-Security-Policy': pol, 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-cache' };
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404, { ...h, 'Content-Type': TYPES['.html'] }); res.end(fs.readFileSync(path.join(OUT, '404.html'))); return; }
    res.writeHead(200, { ...h, 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
    res.end(data);
  });
});

// in the page: every visible text element against the background it sits on
function contrastAudit() {
  function rgb(s) { const m = s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; }
  function lum(c) { return [c.r, c.g, c.b].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }).reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0); }
  function bg(el) { for (let n = el; n; n = n.parentElement) { const c = rgb(getComputedStyle(n).backgroundColor); if (c && c.a > 0.5) return c; } return rgb(getComputedStyle(document.body).backgroundColor) || { r: 255, g: 255, b: 255 }; }
  const bad = [];
  document.querySelectorAll('p, a, li, h1, h2, h3, label, button, code, pre, th, td, span, figcaption, select, input, textarea, summary').forEach((el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none') return;
    if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && !/^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName)) return;
    if (el.closest('svg, .withheld-ok')) return;
    const fg = rgb(cs.color); if (!fg) return;
    const b = bg(el), L1 = lum(fg), L2 = lum(b), ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const size = parseFloat(cs.fontSize), large = size >= 24 || (size >= 18.66 && +cs.fontWeight >= 700);
    if (ratio < (large ? 3 : 4.5)) bad.push(el.tagName.toLowerCase() + '.' + el.className + ' "' + el.textContent.trim().slice(0, 30) + '" ' + ratio.toFixed(2));
  });
  return bad;
}

(async () => {
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const base = 'http://127.0.0.1:' + server.address().port;
  const browser = await chromium.launch();
  if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });

  async function open(url, opt) {
    const ctx = await browser.newContext({ viewport: { width: opt.w, height: opt.h || 900 }, colorScheme: opt.scheme || 'light', javaScriptEnabled: opt.js !== false });
    const page = await ctx.newPage();
    const errors = [], foreign = [];
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('request', (r) => { if (!r.url().startsWith(base) && !r.url().startsWith('data:') && !r.url().startsWith('blob:')) foreign.push(r.url()); });
    await page.goto(base + url, { waitUntil: 'networkidle' });
    return { ctx, page, errors, foreign };
  }

  // 1. every page, every width, both schemes
  // QUICK=1 (the prove-red plants): two widths, light only
  const WIDTHS = process.env.QUICK === '1' ? [390, 1280] : [390, 1280, 1920], SCHEMES = process.env.QUICK === '1' ? ['light'] : ['light', 'dark'];
  for (const w of WIDTHS) for (const scheme of SCHEMES) for (const pg of ['/', '/demo.html', '/colophon.html']) {
    const { ctx, page, errors, foreign } = await open(pg, { w, scheme });
    if (pg === '/' && w >= 760) await page.waitForSelector('#topology[data-ready="1"]', { timeout: 15000 }).catch(() => ok(false, `${pg} ${w} ${scheme}: the drawing app said it was ready`));
    await page.waitForTimeout(300);
    const sw = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
    ok(sw[0] <= sw[1], `${pg} ${w} ${scheme}: no sideways scroll (${sw[0]} > ${sw[1]})`);
    ok(errors.length === 0, `${pg} ${w} ${scheme}: no console errors: ${errors.slice(0, 3).join(' | ')}`);
    ok(foreign.length === 0, `${pg} ${w} ${scheme}: no request to another host: ${foreign.slice(0, 3).join(' ')}`);
    const bad = await page.evaluate(contrastAudit);
    ok(bad.length === 0, `${pg} ${w} ${scheme}: text contrast AA: ${bad.slice(0, 4).join(' ; ')}`);
    if (pg === '/') {
      const vis = await page.evaluate(() => [getComputedStyle(document.querySelector('.stage-app') || document.body).display, getComputedStyle(document.querySelector('.flowfig')).display]);
      if (w >= 760) ok(vis[0] !== 'none' && vis[1] === 'none', `${w}: the drawing app shows, the figure steps aside`);
      else ok(vis[0] === 'none' && vis[1] !== 'none', `${w}: on a phone the figure shows, not the app`);
    }
    if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${(pg.replace(/\W+/g, '') || 'index')}-${w}-${scheme}.png`), fullPage: true });
    await ctx.close();
  }

  // 2. the demo, worked
  {
    const { ctx, page, errors, foreign } = await open('/demo.html', { w: 1280 });
    const status = () => page.$eval('#rt', (n) => [n.textContent, n.className]);
    let st = await status();
    ok(/identical, byte for byte/.test(st[0]) && /ok/.test(st[1]), 'demo: the sample round-trips, said in words: ' + st[0]);
    ok(await page.evaluate(() => window.obsmageDemo.roundTrip()), 'demo: atoms -> file -> atoms is byte for byte');
    // every joined INI file is the sample, byte for byte; JSON is the same document
    const exact = await page.evaluate(() => {
      const S = window.obsmageDemo.state, sample = JSON.parse(document.getElementById('sample').textContent).files;
      // JSON: the same document (omg_atoms promises parse-equal, not the original key order)
      const canon = (v) => Array.isArray(v) ? v.map(canon) : v && typeof v === 'object' ? Object.keys(v).sort().reduce((o, k) => { o[k] = canon(v[k]); return o; }, {}) : v;
      return Object.keys(sample).map((r) => [r, r.endsWith('.ini') ? S.files[r] === sample[r] : JSON.stringify(canon(JSON.parse(S.files[r]))) === JSON.stringify(canon(JSON.parse(sample[r])))]);
    });
    exact.forEach(([r, same]) => ok(same, `demo: ${r} joins back to the sample`));
    // withheld values stay withheld
    let view = await page.$eval('#file-view', (n) => n.textContent);
    const all = await page.evaluate(() => Object.values(window.obsmageDemo.state.files).join('\n'));
    ok(/FAKE/.test(all), 'demo: the joined files carry the (made-up) credentials, from the vault');
    await page.selectOption('#file-pick', 'basic/profiles/Sample_Studio/basic.ini');
    view = await page.$eval('#file-view', (n) => n.textContent);
    ok(!/FAKE/.test(view) && /withheld, 22 characters/.test(view), 'demo: the file view masks withheld values');
    await page.check('#reveal');
    ok(/FAKEtwitchToken/.test(await page.$eval('#file-view', (n) => n.textContent)), 'demo: "Show withheld values" shows them, here only');
    await page.uncheck('#reveal');
    await page.selectOption('#set-pick', 'basic/profiles/Sample_Studio/basic.ini/set-Twitch.kv');
    const tok = await page.$$eval('#atom-list input', (ns) => ns.map((n) => [n.value, n.readOnly]));
    ok(tok.some(([v, ro]) => v === '@secret(len=22)' && ro), 'demo: the token atom reads @secret(len=22) and cannot be edited');
    // an edit shows in the file, and round-trips
    await page.selectOption('#set-pick', 'basic/profiles/Sample_Studio/basic.ini/set-Video.kv');
    const bx = page.locator('#atom-list input').first();
    await bx.fill('2560');
    view = await page.$eval('#file-view', (n) => n.textContent);
    ok(/BaseCX=2560/.test(view), 'demo: an edited atom shows in the joined file');
    ok(await page.$$eval('#file-view .changed', (ns) => ns.length) === 1, 'demo: exactly the changed line is marked');
    st = await status();
    ok(/identical/.test(st[0]), 'demo: still byte for byte after the edit');
    await bx.fill('1920');
    ok(await page.evaluate(() => { const S = window.obsmageDemo.state; return S.files['basic/profiles/Sample_Studio/basic.ini'] === JSON.parse(document.getElementById('sample').textContent).files['basic/profiles/Sample_Studio/basic.ini']; }),
       'demo: edited back, basic.ini is the sample again, byte for byte (BOM and CRLF kept)');
    // a typed atom refuses what is not JSON
    await page.selectOption('#set-pick', 'basic/profiles/Sample_Studio/service.json/_all.kv');
    const before = await page.evaluate(() => window.obsmageDemo.state.files['basic/profiles/Sample_Studio/service.json']);
    const srv = page.locator('#atom-list input').nth(1);
    await srv.fill('rtmp://no quotes');
    ok(await srv.getAttribute('aria-invalid') === 'true', 'demo: a typed atom that is not JSON is marked invalid');
    ok(await page.evaluate((b) => window.obsmageDemo.state.files['basic/profiles/Sample_Studio/service.json'] === b, before), 'demo: the file keeps the last good value');
    await srv.fill('"rtmp://live.example.invalid/app"');
    // the screen map: keys and drag move a screen and write its atoms
    const sel = '#scene .scene-item[data-item="0"]';
    const x0 = await page.evaluate(() => window.obsmageDemo.state.map.map.items[0].x);
    await page.focus(sel);
    await page.keyboard.press('ArrowRight');
    const x1 = await page.evaluate(() => window.obsmageDemo.state.map.map.items[0].x);
    ok(Math.abs(x1 - x0 - 4) < 0.11, `demo: ArrowRight moves the screen 4 pixels (${x0} -> ${x1})`);
    ok(await page.evaluate(() => document.activeElement && document.activeElement.getAttribute('data-item') === '0'), 'demo: focus stays on the moved screen');
    ok(new RegExp('"x": ' + x1.toFixed(1).replace('.', '\\.')).test(await page.$eval('#file-view', (n) => n.textContent)), 'demo: the moved position is in the joined scene file');
    const box = await page.locator(sel + ' rect').boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down(); await page.mouse.move(box.x + box.width / 2 + 60, box.y + box.height / 2 + 30, { steps: 6 }); await page.mouse.up();
    const x2 = await page.evaluate(() => window.obsmageDemo.state.map.map.items[0].x);
    ok(x2 > x1 + 20, `demo: dragging the screen moves it (${x1} -> ${x2})`);
    ok(await page.evaluate(() => window.obsmageDemo.roundTrip()), 'demo: byte for byte after moving screens');
    // the composer's proposal
    const auditBefore = await page.$$eval('#audit li.b-id', (ns) => ns.length);
    await page.click('#bind');
    const plan = await page.$eval('#plan', (n) => n.textContent);
    ok(/monitor_id/.test(plan) && /Right screen/.test(plan), 'demo: the composer proposes the stable id, and names the unbound capture for a person to decide');
    await page.click('#plan button:first-of-type');
    ok(await page.$$eval('#audit li.b-id', (ns) => ns.length) === auditBefore + 1, 'demo: after adding, one more capture is bound by id');
    ok(await page.$$eval('#atom-list label', (ns) => ns.some((n) => /monitor_id/.test(n.textContent))), 'demo: the added atom is in the list');
    ok(/identical/.test((await status())[0]), 'demo: byte for byte after the composer\'s atoms');
    // your own files, pasted: split here, nothing sent
    await page.selectOption('#own-kind', 'global.ini');
    await page.fill('#own-text', '[General]\nName=Mine\n[OBSWebSocket]\nServerPassword=hunter2hunter2\n');
    await page.click('#own-go');
    const said = await page.$eval('#own-say', (n) => n.textContent);
    ok(/1 credential withheld/.test(said) && /Nothing was sent/.test(said), 'demo: a pasted file is split here and its password withheld: ' + said);
    ok(/have not left this page/.test((await status())[0]), 'demo: the status says the files stayed here');
    await page.selectOption('#set-pick', 'global.ini/set-OBSWebSocket.kv');
    ok(await page.$$eval('#atom-list input', (ns) => ns.some((n) => n.value === '@secret(len=14)')), 'demo: the pasted password is an @secret atom');
    await page.click('#sample-go');
    ok(errors.length === 0, 'demo: no console errors while worked: ' + errors.slice(0, 3).join(' | '));
    ok(foreign.length === 0, 'demo: no request to another host while worked');
    if (SHOTS) await page.screenshot({ path: path.join(SHOTS, 'demo-worked-1280.png'), fullPage: true });
    await ctx.close();
  }

  // 3. the demo on a phone, by touch-sized keys
  {
    const { ctx, page, errors } = await open('/demo.html', { w: 390, scheme: 'dark' });
    await page.focus('#scene .scene-item[data-item="1"]');
    await page.keyboard.press('Shift+ArrowDown');
    ok(await page.evaluate(() => window.obsmageDemo.roundTrip()), 'demo at 390: byte for byte after Shift+ArrowDown');
    const small = await page.$$eval('button, select, input[type=file]', (ns) => ns.filter((n) => n.offsetParent && n.getBoundingClientRect().height < 24).length);
    ok(small === 0, 'demo at 390: no control shorter than 24 px');
    ok(errors.length === 0, 'demo at 390: no console errors');
    await ctx.close();
  }

  // 4. scripts off: the pages still read, and say what the scripts would do
  for (const pg of ['/', '/demo.html']) {
    const { ctx, page, errors } = await open(pg, { w: 390, js: false });
    const sw = await page.evaluate(() => 0).catch(() => null);
    const text = await page.textContent('body');
    ok(pg === '/' ? /Every setting a line you can read/.test(text) : /Scripts are off/.test(text) && /global\.ini/.test(text), `${pg} scripts off: the page still says what it is`);
    ok(errors.length === 0, `${pg} scripts off: no console errors`);
    if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${pg.replace(/\W+/g, '') || 'index'}-noscript-390.png`), fullPage: true });
    void sw;
    await ctx.close();
  }

  // 5. an unknown address answers the 404 page
  {
    const { ctx, page } = await open('/no-such-page', { w: 1280 });
    ok(/Nothing here/.test(await page.textContent('h1')), 'an unknown address shows the 404 page');
    await ctx.close();
  }

  await browser.close();
  server.close();
  console.log(`browser: ${passes} passed, ${fails} failed`);
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
