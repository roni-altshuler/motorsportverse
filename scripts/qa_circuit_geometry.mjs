// Actual static exports, actual saved data. No fixture circuit or dev server.
import { chromium } from '../projects/f2-predictions/website/node_modules/playwright/index.mjs';
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = resolve(process.argv[2] || '/tmp/motorsport-circuit-browser');
await mkdir(output, { recursive: true });
const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2', '.jpg': 'image/jpeg' };
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', args: ['--no-sandbox'] });
const results = [];
try {
  for (const [series, rounds] of [['f1', [8, 9, 11, 1]], ['f2', [6, 7, 9, 1]], ['f3', [4, 5, 7, 1]]]) {
    const exported = resolve(root, `projects/${series}-predictions/website/out`);
    const server = createServer(async (request, response) => {
      try {
        let pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
        if (pathname.endsWith('/')) pathname += 'index.html';
        let file = resolve(exported, `.${pathname}`);
        if (!file.startsWith(`${exported}/`)) throw new Error('invalid path');
        let bytes;
        try { bytes = await readFile(file); }
        catch {
          // F1 exports /race/9.html; sibling sites export /race/9/index.html.
          const alternate = pathname.endsWith('/index.html') ? pathname.replace(/\/index\.html$/, '.html') : `${pathname}.html`;
          file = resolve(exported, `.${alternate}`);
          if (!file.startsWith(`${exported}/`)) throw new Error('invalid path');
          bytes = await readFile(file);
        }
        response.writeHead(200, { 'Content-Type': mime[extname(file)] || 'application/octet-stream' });
        response.end(bytes);
      } catch { response.writeHead(404); response.end('Not found'); }
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const url = `http://127.0.0.1:${server.address().port}`;
    try {
      for (const [size, viewport] of [['desktop', { width: 1440, height: 1000 }], ['mobile', { width: 390, height: 844 }]]) {
        for (const motion of ['reduce', 'no-preference']) {
          const context = await browser.newContext({ viewport, reducedMotion: motion });
          const page = await context.newPage();
          await page.clock.setFixedTime(new Date('2026-10-06T12:00:00Z'));
          const errors = [], missingResources = [], requests = [];
          page.on('pageerror', error => errors.push({ kind: 'pageerror', message: error.message }));
          page.on('console', message => { if (message.type() === 'error') errors.push({ kind: 'console', message: message.text() }); });
          page.on('response', response => { if (response.status() >= 400) missingResources.push({ url: response.url(), status: response.status() }); });
          page.on('request', request => requests.push(request.url()));
          for (const round of rounds) {
            assert.equal((await page.goto(`${url}/race/${round}/`, { waitUntil: 'networkidle' })).status(), 200);
            if (series !== 'f1') {
              const disclosure = page.getByText('Venue & circuit', { exact: true });
              await disclosure.focus();
              await page.keyboard.press('Enter');
              assert.equal(await disclosure.evaluate(element => element.parentElement.open), true);
            }
            const state = page.getByRole('status', { name: 'Circuit map availability' });
            await state.waitFor({ state: 'visible' });
            assert.match(await state.innerText(), /Circuit map unavailable.*A verified layout is not published/is);
            assert.equal(await page.getByRole('img', { name: 'Circuit layout', exact: true }).count(), 0);
            assert.equal(await state.locator('svg, img, button, a').count(), 0);
            assert.equal(await state.evaluate(element => getComputedStyle(element).animationName), 'none');
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
            const parent = state.locator('..');
            const box = await state.boundingBox(), parentBox = await parent.boundingBox();
            assert.ok(box && parentBox && box.height <= parentBox.height, `${series}/${round}/${size} clipped map state`);
            assert.equal(await page.locator('[data-nextjs-dialog], .vite-error-overlay').count(), 0);
            if (round === rounds[1] && motion === 'reduce') {
              const capture = series === 'f1' ? state.locator('xpath=ancestor::section[1]') : state.locator('xpath=ancestor::div[header][1]');
              await capture.screenshot({ path: resolve(output, `${series}-${size}.png`) });
            }
            if (series !== 'f1') {
              const disclosure = page.getByText('Venue & circuit', { exact: true });
              await disclosure.focus(); await page.keyboard.press('Enter');
              assert.equal(await state.isVisible(), false);
              await page.keyboard.press('Enter');
              await state.waitFor({ state: 'visible' });
            }
            // Offscreen/closed absence has no renderer or replay to run.
            await page.evaluate(() => scrollTo(0, 0));
            assert.equal(requests.filter(request => request.includes('/data/replays/')).length, 0);
          }
          await page.goto(url, { waitUntil: 'networkidle' });
          assert.equal(await page.locator('.hero-track-ribbon').count(), 0);
          assert.equal(requests.filter(request => request.includes('/data/replays/')).length, 0);
          results.push({ series, viewport: size, motion, rounds, mapRejected: true, keyboardDisclosure: series === 'f1' ? 'not applicable (static state)' : 'passed', clipped: false, horizontalOverflow: false, mapAnimation: 'none', replayRequests: 0, errors, missingResources });
          await context.close();
        }
      }
    } finally { await new Promise(resolve => server.close(resolve)); }
  }
} finally { await browser.close(); }
await writeFile(resolve(output, 'browser-qa.json'), `${JSON.stringify(results, null, 2)}\n`);
console.log(JSON.stringify(results.map(({ errors, missingResources, ...result }) => ({ ...result, browserErrors: errors.length, missingResources: missingResources.length })), null, 2));
