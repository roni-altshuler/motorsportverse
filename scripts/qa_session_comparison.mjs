// Actual static-export browser QA. Negative states explicitly inject faults
// into the one local JSON response; the successful flow uses the served file.
// Run after the F1 build: node scripts/qa_session_comparison.mjs [output-dir]
import { chromium } from '../projects/f1-predictions/website/node_modules/playwright/index.mjs';
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const root = fileURLToPath(new URL('../', import.meta.url));
const exported = resolve(root, 'projects/f1-predictions/website/out');
const output = resolve(process.argv[2] || '/tmp/motorsport-lap-comparison-qa');
await mkdir(output, { recursive: true });
const fixture = JSON.parse(await readFile(resolve(exported, 'data/session-comparison/2025_Monaco_R.json'), 'utf8'));
const mime = { '.html': 'text/html', '.txt': 'text/plain', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2', '.jpg': 'image/jpeg', '.ico': 'image/x-icon' };
const server = createServer(async (request, response) => {
  try {
    let pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    let file = resolve(exported, `.${pathname.endsWith('/') ? `${pathname}index.html` : pathname}`);
    if (!file.startsWith(`${exported}/`)) throw new Error('invalid path');
    let bytes;
    try { bytes = await readFile(file); }
    catch {
      if (extname(file)) throw new Error('missing asset');
      file += '.html'; bytes = await readFile(file);
    }
    response.writeHead(200, { 'Content-Type': mime[extname(file)] || 'application/octet-stream' });
    response.end(bytes);
  } catch { response.writeHead(404); response.end('Not found'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const archive = '**/data/session-comparison/2025_Monaco_R.json';
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', args: ['--no-sandbox'] });
const results = [];
const unique = values => [...new Map(values.map(value => [JSON.stringify(value), value])).values()];
async function capture(page, name) {
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name}: horizontal overflow`);
  // Reset the viewport before a full-page capture so sticky navigation is not
  // painted midway through the document after a control scrolled into focus.
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: 'instant' }));
  await page.waitForFunction(() => window.scrollY < 2);
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await page.screenshot({ path: resolve(output, `${name}.png`), fullPage: true, animations: 'disabled' });
}
try {
  for (const [size, viewport, reducedMotion] of [
    ['desktop', { width: 1440, height: 1000 }, 'no-preference'],
    ['mobile', { width: 390, height: 844 }, 'reduce'],
  ]) {
    const context = await browser.newContext({ viewport, reducedMotion });
    const page = await context.newPage();
    const errors = [], requests = [], missing = [];
    page.on('pageerror', error => errors.push({ kind: 'pageerror', message: error.message }));
    page.on('console', message => { if (message.type() === 'error') errors.push({ kind: 'console', message: message.text(), url: message.location().url }); });
    page.on('response', response => {
      if (response.url().includes('/session-comparison/')) requests.push({ url: response.url().replace(base, ''), status: response.status() });
      if (response.status() >= 400) missing.push({ url: response.url().replace(base, ''), status: response.status() });
    });
    assert.equal((await page.goto(`${base}/compare/laps`, { waitUntil: 'networkidle' })).status(), 200);
    await page.getByLabel('Driver A', { exact: true }).waitFor();
    const a = page.getByLabel('Driver A', { exact: true }), b = page.getByLabel('Driver B', { exact: true });
    assert.equal(await a.inputValue(), 'NOR'); assert.equal(await b.inputValue(), 'RUS');
    assert.equal(await a.locator('option').count(), 20);
    assert.equal(await page.getByLabel('Lap delta +0.184s').count(), 1);
    assert.match(await page.getByRole('main').innerText(), /2025 archive/i);
    assert.ok((await page.getByRole('main').innerText()).includes('not a controlled pace test'));
    assert.equal(requests[0].status, 200);
    const comparisonBeforeNavigation = { errors: unique(errors), missingResources: unique(missing) };
    await capture(page, `${size}-comparison`);

    await a.focus();
    const focus = await a.evaluate(element => ({ width: getComputedStyle(element).outlineWidth, style: getComputedStyle(element).outlineStyle, offset: getComputedStyle(element).outlineOffset }));
    assert.equal(focus.width, '2px'); assert.equal(focus.style, 'solid');
    await capture(page, `${size}-keyboard-focus`);
    await page.keyboard.press('Tab');
    assert.equal(await page.getByRole('button', { name: 'Swap drivers' }).evaluate(element => element === document.activeElement), true);
    await page.keyboard.press('Enter');
    assert.equal(await a.inputValue(), 'RUS'); assert.equal(await b.inputValue(), 'NOR');
    assert.equal(await page.getByLabel('Lap delta −0.184s').count(), 1);
    await page.keyboard.press('Tab');
    assert.equal(await b.evaluate(element => element === document.activeElement), true);
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    assert.equal(await b.inputValue(), 'RUS');
    // Selecting the other lane exchanges drivers rather than creating a self-comparison.
    await a.selectOption('NOR'); assert.equal(await b.inputValue(), 'RUS');
    const flows = ['real JSON 200 / 20 drivers', 'default pair / +0.184s', 'keyboard focus / swap / native selection / signed delta', 'duplicate choice exchanges lanes'];
    for (const code of ['LEC', 'HAM', 'TSU', 'GAS', 'NOR', 'RUS', 'NOR']) {
      await a.selectOption(code);
      assert.notEqual(await a.inputValue(), await b.inputValue());
      const expectedA = fixture.drivers.find(driver => driver.code === code);
      const selectedB = await b.inputValue();
      const expectedB = fixture.drivers.find(driver => driver.code === selectedB);
      const delta = expectedB.lapMs - expectedA.lapMs;
      const formatted = `${delta > 0 ? '+' : delta < 0 ? '−' : ''}${(Math.abs(delta) / 1000).toFixed(3)}s`;
      assert.equal(await page.getByLabel(`Lap delta ${formatted}`).count(), 1);
      if (code === 'TSU') {
        assert.equal(await page.getByRole('main').locator('img[src*="TSU"]').count(), 0);
        await capture(page, `${size}-portrait-fallback`);
      }
    }
    flows.push('seven repeated selections / actual stored deltas / missing portrait fallback');
    await page.getByText('Archive source', { exact: true }).focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.getByRole('main').locator('details').evaluate(element => element.open), true);
    await page.getByRole('main').getByRole('link', { name: 'Season calendar' }).click();
    await page.waitForURL('**/calendar');
    await page.getByRole('main').waitFor();
    if (size === 'desktop') {
      await page.getByRole('button', { name: 'Races', exact: true }).hover();
    } else {
      await page.getByRole('button', { name: /Open menu/ }).click();
    }
    await page.getByRole('link', { name: /lap comparison · 2025 archive/i }).click();
    await page.waitForURL('**/compare/laps');
    await page.getByLabel('Driver A', { exact: true }).waitFor();
    await page.goBack({ waitUntil: 'networkidle' });
    await page.waitForURL('**/calendar');
    await page.goForward({ waitUntil: 'networkidle' });
    await page.getByLabel('Driver A', { exact: true }).waitFor();
    flows.push('calendar navigation / desktop or mobile menu / history back-forward');
    if (size === 'desktop') {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await a.selectOption('LEC');
      assert.equal(await page.getByRole('main').evaluate(element => element.getAnimations({ subtree: true }).length), 0);
      await capture(page, 'desktop-reduced-motion');
      flows.push('reduced-motion selection / zero comparison animations');
    }
    assert.equal(errors.filter(error => error.kind === 'pageerror').length, 0);
    assert.equal(missing.filter(resource => resource.url.startsWith('/')).length, 0);
    results.push({ viewport: size, fixtureInjection: false, flows, focus, requests, comparisonBeforeNavigation, errors: unique(errors), missingResources: unique(missing), horizontalOverflow: false });
    await context.close();
  }
  // Explicit fault injections retain the real local-session body for recovery.
  for (const state of ['loading', 'http-error-retry', 'empty', 'wrong-session']) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    let count = 0, release;
    const gate = new Promise(resolve => { release = resolve; });
    await page.route(archive, async route => {
      count++;
      if (state === 'loading' && count === 1) await gate;
      if (state === 'http-error-retry' && count === 1) return route.fulfill({ status: 503, body: 'QA fault injection' });
      const data = structuredClone(fixture);
      if (state === 'empty') data.drivers = [];
      if (state === 'wrong-session') data.session.season = 2026;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
    });
    await page.goto(`${base}/compare/laps`, { waitUntil: 'domcontentloaded' });
    if (state === 'loading') {
      await page.getByRole('status').filter({ hasText: 'Loading the 2025 Monaco' }).waitFor();
      await capture(page, 'mobile-loading'); release();
      await page.getByLabel('Driver A', { exact: true }).waitFor();
    } else if (state === 'empty') {
      await page.getByRole('heading', { name: 'No comparison available' }).waitFor();
      assert.equal(await page.getByLabel('Driver A', { exact: true }).count(), 0);
      await capture(page, 'mobile-empty');
    } else {
      await page.getByRole('main').getByRole('alert').waitFor();
      assert.equal(await page.getByLabel('Driver A', { exact: true }).count(), 0);
      await capture(page, `mobile-${state}`);
      if (state === 'http-error-retry') {
        await page.getByRole('button', { name: 'Try again' }).focus();
        await page.keyboard.press('Enter');
        await page.getByLabel('Driver A', { exact: true }).waitFor();
        assert.equal(count, 2);
        assert.equal(await page.getByLabel('Lap delta +0.184s').count(), 1);
      }
    }
    results.push({ viewport: 'mobile', fixtureInjection: true, state, passed: true });
    await context.close();
  }
} finally {
  await writeFile(resolve(output, 'browser-qa.json'), `${JSON.stringify(results, null, 2)}\n`);
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
console.log(JSON.stringify(results, null, 2));
