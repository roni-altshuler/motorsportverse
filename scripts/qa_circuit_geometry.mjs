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
async function shiftWallClock(context) {
  // Shift only the advancing wall clock. Mocking performance/RAF interferes
  // with native Web Animations used by the existing hero entrance effects.
  await context.addInitScript(() => {
    const NativeDate = Date, startedAt = NativeDate.now();
    const epoch = NativeDate.parse(location.pathname === '/' ? '2026-06-05T12:00:00Z' : '2026-10-06T12:00:00Z');
    const now = () => epoch + NativeDate.now() - startedAt;
    globalThis.Date = new Proxy(NativeDate, {
      construct(target, args) { return Reflect.construct(target, args.length ? args : [now()]); },
      apply() { return new NativeDate(now()).toString(); },
      get(target, key) { return key === 'now' ? now : Reflect.get(target, key); },
    });
  });
}

const results = [];
const heroOnly = process.argv.includes("--hero-only");
const copyOnly = process.argv.includes("--copy-only");
assert.equal(heroOnly && copyOnly, false, 'Choose one focused browser mode');
try {
  for (const [series, rounds] of [['f1', [8, 9, 6, 11, 1]], ['f2', [6, 7, 4, 9, 1, 2]], ['f3', [4, 5, 2, 7, 1]]]) {
    if (heroOnly && series !== 'f1') continue;
    if (copyOnly && series === 'f1') continue;
    const activeRounds = heroOnly ? [] : copyOnly ? [rounds[1], rounds[2]] : rounds;
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
        for (const motion of copyOnly ? ['reduce'] : ['reduce', 'no-preference']) {
          const context = await browser.newContext({ viewport, reducedMotion: motion });
          await shiftWallClock(context);
          let page = await context.newPage();
          const errors = [], missingResources = [], requests = [];
          const circuitCopy = [];
          const observe = target => {
            target.on('pageerror', error => errors.push({ kind: 'pageerror', message: error.message }));
            target.on('console', message => { if (message.type() === 'error') errors.push({ kind: 'console', message: message.text() }); });
            target.on('response', response => { if (response.status() >= 400) missingResources.push({ url: response.url(), status: response.status() }); });
            target.on('request', request => requests.push(request.url()));
          };
          observe(page);
          for (const round of activeRounds) {
            console.log(JSON.stringify({ checking: series, round, size, motion }));
            assert.equal((await page.goto(`${url}/race/${round}/`, { waitUntil: 'networkidle' })).status(), 200);
            if (series !== 'f1') {
              const disclosure = page.getByText('Venue & circuit', { exact: true });
              await disclosure.focus();
              await page.keyboard.press('Enter');
              assert.equal(await disclosure.evaluate(element => element.parentElement.open), true);
            }
            const quarantined = rounds.indexOf(round) < 2;
            const unavailable = quarantined || (series === 'f2' && round === 2);
            const state = unavailable
              ? page.getByRole('status', { name: 'Circuit map availability' })
              : page.getByRole('img', { name: 'Circuit layout', exact: true }).first();
            await state.waitFor({ state: 'visible' });
            if (unavailable) {
              assert.match(await state.innerText(), /Circuit map unavailable.*A circuit layout is not available/is);
              assert.equal(await page.getByRole('img', { name: 'Circuit layout', exact: true }).count(), 0);
              assert.equal(await state.locator('svg, img, button, a').count(), 0);
            } else {
              assert.ok(await state.locator('path').first().getAttribute('d'));
              await page.getByText('Layout review pending', { exact: true }).first().waitFor();
              if (round === rounds[3] && series !== 'f1') {
                const labels = await state.locator('text').allTextContents();
                assert.equal(labels.length, 12);
                assert.equal(labels.includes('1') || labels.includes('12'), false);
              }
            }
            if (series !== 'f1') {
              const section = page.getByText('Venue & circuit', { exact: true }).locator('..');
              const text = (await section.innerText()).replace(/\s+/g, ' ').trim();
              assert.doesNotMatch(text, /\bverified\b/i);
              assert.ok(text.includes('An interactive circuit explorer requires a reviewed layout and is not available here.'));
              assert.ok(text.includes(unavailable
                ? 'No circuit outline is available for this event.'
                : 'This existing circuit outline is retained while layout review is pending.'));
              circuitCopy.push({ round, outline: unavailable ? 'unavailable' : 'legacy-unreviewed', text });
              if (copyOnly) await section.screenshot({ path: resolve(output, `${series}-${unavailable ? 'unavailable' : 'retained'}-copy-${size}.png`) });
            }
            assert.equal(await state.evaluate(element => getComputedStyle(element).animationName), 'none');
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
            const parent = state.locator('..');
            const box = await state.boundingBox(), parentBox = await parent.boundingBox();
            assert.ok(box && parentBox && box.height <= parentBox.height, `${series}/${round}/${size} clipped map state`);
            assert.equal(await page.locator('[data-nextjs-dialog], .vite-error-overlay').count(), 0);
            if (!copyOnly && (round === rounds[1] || round === rounds[2]) && motion === 'reduce') {
              const capture = series === 'f1' ? state.locator('xpath=ancestor::section[1]') : state.locator('xpath=ancestor::div[header][1]');
              await capture.screenshot({ path: resolve(output, `${series}-${round === rounds[2] ? 'preserved-' : ''}${size}.png`) });
            }
            if (series !== 'f1') {
              const disclosure = page.getByText('Venue & circuit', { exact: true });
              await disclosure.focus(); await page.keyboard.press('Enter');
              assert.equal(await state.isVisible(), false);
              await page.keyboard.press('Enter');
              await state.waitFor({ state: 'visible' });
            }
            // New explorer/replay payloads are never fetched by these legacy surfaces.
            await page.evaluate(() => scrollTo(0, 0));
            assert.equal(requests.filter(request => request.includes('/data/replays/')).length, 0);
          }
          let hero = null;
          if (series === 'f1' && heroOnly) {
            // This historical home scenario gets a fresh context: do not jump
            // months backward in a tab already used for October race cases.
            const heroContext = await browser.newContext({ viewport, reducedMotion: motion });
            await shiftWallClock(heroContext);
            page = await heroContext.newPage();
            observe(page);
            // Select the real existing Monaco event, not a fixture or intercepted payload.
            await page.goto(url, { waitUntil: 'networkidle' });
            const heading = page.getByRole('heading', { name: 'Read the grid before lights out', exact: true });
            await heading.waitFor({ state: 'visible' });
            await page.waitForFunction(() => {
              let element = document.querySelector('.hero-photo-band h1');
              while (element) {
                if (Number(getComputedStyle(element).opacity) < 0.9) return false;
                element = element.parentElement;
              }
              return true;
            });
            await heading.evaluate(async element => {
              const animations = [];
              for (let node = element; node; node = node.parentElement)
                animations.push(...node.getAnimations().filter(animation => animation.effect?.getComputedTiming().iterations !== Infinity));
              await Promise.all(animations.map(animation => animation.finished.catch(() => {})));
              await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            });
            const ribbon = page.locator('.hero-track-ribbon');
            await ribbon.waitFor({ state: 'visible' });
            const raw = JSON.parse(await readFile(resolve(root, 'projects/f1-predictions/website/public/data/rounds/round_06.json'), 'utf8'));
            const sweep = ribbon.locator('.ribbon-sweep');
            assert.equal(await sweep.getAttribute('d'), raw.circuitInfo.geometry.path);
            const before = await sweep.evaluate(element => ({
              offset: parseFloat(getComputedStyle(element).strokeDashoffset),
              duration: parseFloat(getComputedStyle(element).animationDuration),
              iterations: getComputedStyle(element).animationIterationCount,
            }));
            await page.waitForTimeout(300);
            const after = await sweep.evaluate(element => parseFloat(getComputedStyle(element).strokeDashoffset));
            if (motion === 'reduce') {
              assert.ok(before.duration <= 0.001);
              assert.equal(before.iterations, '1');
              assert.ok(Math.abs(after - before.offset) < 0.01);
            } else {
              assert.equal(before.duration, 14);
              assert.equal(before.iterations, 'infinite');
              assert.ok(Math.abs(after - before.offset) > 1);
            }
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
            await page.evaluate(() => scrollTo(0, 0));
            await page.waitForTimeout(200);
            const headline = await heading.evaluate(element => {
              const style = getComputedStyle(element), box = element.getBoundingClientRect();
              return { color: style.color, opacity: style.opacity, visibility: style.visibility, x: box.x, y: box.y, width: box.width, height: box.height };
            });
            assert.ok(headline.y >= 0 && headline.y + headline.height <= viewport.height);
            await page.screenshot({ path: resolve(output, `f1-hero-${size}-${motion}.png`) });
            hero = { event: 'Monaco', realStoredPath: true, present: true, headlineVisible: true, headline, duration: before.duration, iterations: before.iterations, dashOffsetChanged: Math.abs(after - before.offset) > 1 };
            await heroContext.close();
          }
          assert.equal(requests.filter(request => request.includes('/data/replays/')).length, 0);
          results.push({ series, viewport: size, motion, rounds: activeRounds, quarantined: activeRounds.filter(round => rounds.indexOf(round) < 2), preserved: activeRounds.filter(round => rounds.slice(2, 5).includes(round)), missing: activeRounds.filter(round => rounds.slice(5).includes(round)), ambiguousMarkersSuppressed: activeRounds.includes(rounds[3]) ? true : null, circuitCopy, hero, keyboardDisclosure: series === 'f1' ? 'not applicable (static maps)' : 'passed', clipped: false, horizontalOverflow: false, mapAnimation: 'none', replayRequests: 0, errors, missingResources });
          await context.close();
        }
      }
    } finally { await new Promise(resolve => server.close(resolve)); }
  }
} finally { await browser.close(); }
await writeFile(resolve(output, 'browser-qa.json'), `${JSON.stringify(results, null, 2)}\n`);
console.log(JSON.stringify(results.map(({ errors, missingResources, ...result }) => ({ ...result, browserErrors: errors.length, missingResources: missingResources.length })), null, 2));
