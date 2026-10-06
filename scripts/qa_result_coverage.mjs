// Build each affected site first. Uses existing Playwright + system Chromium.
// node scripts/qa_result_coverage.mjs [screenshot-directory]
import { chromium } from '../projects/f2-predictions/website/node_modules/playwright/index.mjs';
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = resolve(process.argv[2] || '/tmp/motorsport-result-coverage-qa');
await mkdir(output, { recursive: true });
const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2', '.jpg': 'image/jpeg' };
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', args: ['--no-sandbox'] });
const results = [];
const unique = values => [...new Map(values.map(value => [JSON.stringify(value), value])).values()];
try {
  for (const [series, count, firstRound] of [['f2', 6, 7], ['f3', 4, 6], ['indycar', 7, 12]]) {
    const exported = resolve(root, `projects/${series}-predictions/website/out`);
    const server = createServer(async (request, response) => {
      try {
        let pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
        if (pathname.endsWith('/')) pathname += 'index.html';
        const file = resolve(exported, `.${pathname}`);
        if (!file.startsWith(`${exported}/`)) throw new Error('invalid path');
        const bytes = await readFile(file);
        response.writeHead(200, { 'Content-Type': mime[extname(file)] || 'application/octet-stream' });
        response.end(bytes);
      } catch { response.writeHead(404); response.end('Not found'); }
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const url = `http://127.0.0.1:${server.address().port}`;
    try {
      for (const [size, viewport] of [['desktop', { width: 1440, height: 1050 }], ['mobile', { width: 390, height: 844 }]]) {
        const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push({ kind: 'pageerror', url: page.url(), message: error.message }));
        page.on('console', message => { if (message.type() === 'error') errors.push({ kind: 'console', url: page.url(), message: message.text(), location: message.location().url }); });
        const failedRequests = [];
        page.on('requestfailed', request => failedRequests.push({ url: request.url(), error: request.failure()?.errorText }));
        const missingResources = [];
        page.on('response', response => { if (response.status() >= 400) missingResources.push({ url: response.url(), status: response.status() }); });
        // Fixed QA clock makes screenshots and date-boundary assertions repeatable.
        await page.clock.setFixedTime(new Date('2026-10-06T12:00:00Z'));
        assert.equal((await page.goto(url, { waitUntil: 'networkidle' })).status(), 200);
        const panel = page.getByRole('region', { name: 'Result coverage' });
        await panel.getByRole('heading', { name: 'Result coverage is behind' }).waitFor();
        assert.match(await panel.innerText(), new RegExp(`${count} scheduled rounds are past due`));
        assert.match(await panel.innerText(), /Source availability has not been verified here/);
        assert.equal(await page.getByText('Past-due forecast', { exact: true }).count(), 1);
        assert.equal(await page.getByText('Next up', { exact: true }).count(), 0);
        const disclosure = panel.locator('summary');
        await disclosure.focus();
        await page.keyboard.press('Enter');
        assert.equal(await panel.locator('details').evaluate(element => element.open), true);
        assert.equal(await panel.getByRole('link').count(), count);
        await panel.evaluate(element => element.scrollIntoView({ block: 'center' }));
        await page.evaluate(() => window.scrollBy(0, -60));
        await panel.screenshot({ path: resolve(output, `${series}-${size}.png`) });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${series}/${size} horizontal overflow`);
        await panel.getByRole('link').first().click();
        await page.waitForURL(`**/race/${firstRound}/`);
        await page.getByRole('main').waitFor();
        assert.ok((await page.getByRole('main').innerText()).trim().length > 100);
        assert.equal(await page.locator('[data-nextjs-dialog], .vite-error-overlay').count(), 0);
        await page.getByText('Snapshot Forecast', { exact: true }).waitFor();
        assert.equal(await page.getByText('Upcoming Forecast', { exact: true }).count(), 0);
        await page.goBack({ waitUntil: 'networkidle' });
        await page.getByRole('region', { name: 'Result coverage' }).waitFor();
        await page.goForward({ waitUntil: 'networkidle' });
        await page.getByText('Snapshot Forecast', { exact: true }).waitFor();
        // Retain existing asset/network/framework issues instead of hiding them.
        // Assertions above verify the changed feature even on a degraded route.
        results.push({ series, viewport: size, pastDueRounds: count, keyboardDisclosure: 'passed', raceNavigation: 'passed', backForward: 'passed', horizontalOverflow: false, errorsCount: errors.length, failedRequestsCount: failedRequests.length, missingResourcesCount: missingResources.length, errors: unique(errors), failedRequests: unique(failedRequests), missingResources: unique(missingResources) });
        await context.close();
      }
    } finally { await new Promise(resolve => server.close(resolve)); }
  }
} finally { await browser.close(); }
await writeFile(resolve(output, 'browser-qa.json'), `${JSON.stringify(results, null, 2)}\n`);
console.log(JSON.stringify(results.map(({ series, viewport, pastDueRounds, keyboardDisclosure, raceNavigation, horizontalOverflow, errors, failedRequests, missingResources }) => ({ series, viewport, pastDueRounds, keyboardDisclosure, raceNavigation, horizontalOverflow, browserErrors: errors.length, failedRequests: failedRequests.length, missingResources: missingResources.length })), null, 2));
