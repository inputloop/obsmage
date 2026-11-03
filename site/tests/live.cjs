// SPDX-FileCopyrightText: 2026 INPUTLOOP
// SPDX-License-Identifier: GPL-3.0-or-later OR LGPL-3.0-or-later
//
// live.cjs: the site as it is served, from outside. LIVE_URL (https://obsmage.com) at 390, 1280 and
// 1920, light and dark: every page answers, no console error, no request to any host but the site's
// own, no sideways scroll; www lands on the apex; the demo round-trips byte for byte, a screen
// moves; the release feed is the line form and names a bundle that answers. SHOTS=dir keeps screenshots.
//   LIVE_URL=https://obsmage.com SHOTS=/tmp/shots node site/tests/live.cjs
// Behind an intercepting egress proxy set LIVE_PROXY (and LIVE_IGNORE_TLS=1, the certificate then
// being checked elsewhere, as the report says); with neither, nothing is relaxed.
const fs = require('node:fs'), path = require('node:path');
const { chromium } = require('playwright');
const BASE = (process.env.LIVE_URL || 'https://obsmage.com').replace(/\/$/, '');
const HOST = new URL(BASE).host, SHOTS = process.env.SHOTS || '';
let fails = 0, passes = 0;
const ok = (c, d) => { if (c) passes++; else { fails++; console.log('FAIL ' + d); } };
(async () => {
  const launch = process.env.LIVE_PROXY ? { proxy: { server: process.env.LIVE_PROXY } } : {};
  const browser = await chromium.launch(launch);
  if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });
  async function open(url, w, scheme) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, colorScheme: scheme, ignoreHTTPSErrors: process.env.LIVE_IGNORE_TLS === '1' });
    const page = await ctx.newPage(), errors = [], foreign = [];
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('request', (r) => { const u = new URL(r.url()); if (/^https?:$/.test(u.protocol) && u.host !== HOST) foreign.push(r.url()); });
    const res = await page.goto(url, { waitUntil: 'networkidle' });
    return { ctx, page, res, errors, foreign };
  }
  for (const w of [390, 1280, 1920]) for (const scheme of ['light', 'dark']) for (const pg of ['/', '/demo.html', '/colophon.html']) {
    const { ctx, page, res, errors, foreign } = await open(BASE + pg, w, scheme);
    ok(res && res.status() === 200, `${pg} ${w} ${scheme}: 200 (${res && res.status()})`);
    if (pg === '/' && w >= 760) await page.waitForSelector('#topology[data-ready="1"]', { timeout: 20000 }).catch(() => ok(false, `${pg} ${w}: the drawing app said it was ready`));
    await page.waitForTimeout(600);
    const sw = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
    ok(sw[0] <= sw[1], `${pg} ${w} ${scheme}: no sideways scroll (${sw})`);
    ok(errors.length === 0, `${pg} ${w} ${scheme}: no console errors: ${errors.slice(0, 2).join(' | ')}`);
    ok(foreign.length === 0, `${pg} ${w} ${scheme}: nothing from another host: ${foreign.slice(0, 2).join(' ')}`);
    if (pg === '/demo.html') ok(/identical, byte for byte/.test(await page.textContent('#rt')), `demo ${w} ${scheme}: the sample round-trips`);
    if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `live-${pg.replace(/\W+/g, '') || 'index'}-${w}-${scheme}.png`), fullPage: true });
    await ctx.close();
  }
  { // www lands on the apex; the demo worked once more; the feed
    const { ctx, page, res } = await open(BASE.replace('://', '://www.') + '/demo.html', 1280, 'light');
    ok(res && page.url() === BASE + '/demo.html', `www lands on ${BASE}/demo.html (${page.url()})`);
    const x0 = await page.evaluate(() => window.obsmageDemo.state.map.map.items[0].x);
    await page.focus('#scene .scene-item[data-item="0"]'); await page.keyboard.press('Shift+ArrowRight');
    const x1 = await page.evaluate(() => window.obsmageDemo.state.map.map.items[0].x);
    ok(Math.abs(x1 - x0 - 40) < 0.11 && await page.evaluate(() => window.obsmageDemo.roundTrip()), `live demo: a screen moved 40 px and still round-trips (${x0} -> ${x1})`);
    if (SHOTS) await page.screenshot({ path: path.join(SHOTS, 'live-demo-moved-1280.png'), fullPage: true });
    const feed = await page.request.get(BASE + '/dist/channel.json');
    const text = await feed.text();
    ok(feed.status() === 200 && /^\{\n(  "[a-z_0-9]+": "[^"\\]*",\n)*  "[a-z_0-9]+": "[^"\\]*"\n\}\n$/.test(text), 'the feed is the line form');
    const art = (/"artifact": "([^"]+)"/.exec(text) || [])[1];
    const head = art ? await page.request.head(art) : null;
    ok(head && head.status() === 200, `the feed's artifact answers (${art} ${head && head.status()})`);
    await ctx.close();
  }
  await browser.close();
  console.log(`live: ${passes} passed, ${fails} failed`);
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
