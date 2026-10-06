// Build a temporary copy with the explicit homepage-gap fixture and /forecast-gap-qa route.
// node scripts/qa_homepage_forecast_gap.mjs <temporary-export> [screenshot-directory]
import { chromium } from '../projects/f2-predictions/website/node_modules/playwright/index.mjs';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import assert from 'node:assert/strict';

if (!process.argv[2]) throw new Error('Pass the temporary fixture static-export directory.');
const root = resolve(process.argv[2]);
const output = resolve(process.argv[3] || '/tmp/motorsport-homepage-gap-qa');
await mkdir(output, { recursive: true });
const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2' };
const server = createServer(async (request, response) => {
  try {
    let path = new URL(request.url, 'http://localhost').pathname;
    if (path.endsWith('/')) path += 'index.html';
    const file = resolve(root, `.${path}`);
    if (!file.startsWith(root + '/')) throw new Error('invalid path');
    const bytes = await readFile(file);
    response.writeHead(200, { 'Content-Type': mime[extname(file)] || 'application/octet-stream' });
    response.end(bytes);
  } catch { response.writeHead(404); response.end('not found'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch({ executablePath: '/usr/bin/chromium', args: ['--no-sandbox'] });
const results = [];
try {
  for (const [name, viewport] of [['desktop', { width: 1440, height: 1050 }], ['mobile', { width: 390, height: 844 }]]) {
    const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const errors = [];
    const consoleErrors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
    await page.clock.setFixedTime(new Date('2026-10-06T12:00:00Z'));
    assert.equal((await page.goto(`http://127.0.0.1:${server.address().port}/forecast-gap-qa/`, { waitUntil: 'networkidle' })).status(), 200);
    await page.getByRole('note').getByText(/Explicit QA fixture/).waitFor();
    const status = page.getByLabel('Snapshot forecast status');
    await status.getByText('Snapshot forecast', { exact: true }).waitFor();
    await status.getByText('in 60d 12h', { exact: true }).waitFor();
    assert.match(await status.innerText(), /R3/);
    assert.equal(await status.getByText('Past-due forecast', { exact: true }).count(), 0);
    assert.match(await page.getByRole('link', { name: 'View snapshot forecast →' }).getAttribute('href'), /^\/race\/3\/?$/);
    const panel = page.getByRole('region', { name: 'Result coverage' });
    await panel.getByRole('heading', { name: 'Result coverage is behind' }).waitFor();
    assert.match(await panel.innerText(), /1 scheduled round is past due/);
    await panel.locator('summary').focus();
    await page.keyboard.press('Enter');
    assert.match(await panel.getByRole('link', { name: 'R1 · Old coverage gap' }).getAttribute('href'), /^\/race\/1\/?$/);
    assert.equal(await panel.getByRole('link').count(), 1);
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Add the Future forecast F2 round to your calendar' }).click();
    const download = await downloadPromise;
    const calendarFile = `/tmp/motorsport-forecast-gap-${name}.ics`;
    await download.saveAs(calendarFile);
    const ics = await readFile(calendarFile, 'utf8');
    assert.match(ics, /DTSTART;VALUE=DATE:20261206/);
    assert.match(ics, /SUMMARY:Future forecast/);
    assert.ok(!ics.includes('20260801'));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await panel.evaluate(element => element.scrollIntoView({ block: 'center' }));
    await page.evaluate(() => window.scrollBy(0, -80));
    await panel.screenshot({ path: resolve(output, `forecast-gap-coverage-${name}.png`) });
    const forecast = status.locator('..');
    await forecast.evaluate(element => element.scrollIntoView({ block: 'center' }));
    await page.evaluate(() => window.scrollBy(0, -80));
    await forecast.screenshot({ path: resolve(output, `forecast-gap-${name}.png`) });
    results.push({ viewport: name, fixture: 'Explicit QA calendar: old gap R1, later import R2, future forecast R3', actualHomepage: true, displayedRound: 3, snapshotForecast: 'passed', futureCountdown: 'passed', coverageGap: 1, keyboardDisclosure: 'passed', calendarDownloadDate: '2026-12-06', horizontalOverflow: false, errors, consoleErrors: [...new Set(consoleErrors)] });
    await context.close();
  }
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
await writeFile(resolve(output, 'homepage-gap-browser-qa.json'), JSON.stringify(results, null, 2) + '\n');
console.log(JSON.stringify(results.map(({ consoleErrors, ...result }) => ({ ...result, consoleErrorsCount: consoleErrors.length })), null, 2));
