// After npm run build: node scripts/verify-race-centre.mjs [screenshot-directory]
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
import { chromium } from 'playwright';
const root = resolve('out');
const screenshots = process.argv[2] || '/tmp/motorsportverse-review';
await mkdir(screenshots, { recursive: true });
const mime = { '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript', '.json': 'application/json', '.woff2': 'font/woff2', '.png': 'image/png', '.svg': 'image/svg+xml', '.webp': 'image/webp' };
const server = createServer(async (req, res) => {
  try {
    const path = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    let file = resolve(root, `.${path}`);
    if (file !== root && !file.startsWith(root + sep)) throw new Error('Invalid path');
    if (!extname(file)) file = resolve(file, 'index.html');
    res.setHeader('Content-Type', mime[extname(file)] || 'application/octet-stream');
    res.end(await readFile(file));
  } catch { res.writeHead(404); res.end('Not found'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const url = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  page.setDefaultTimeout(60000);
  page.setDefaultNavigationTimeout(120000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.getByRole('heading', { name: /Feel the race/ }).waitFor();
  await page.getByRole('heading', { name: /Your weekend/ }).waitFor();
  const chips = page.locator('.series-filters');
  await chips.getByRole('button', { name: 'Formula 1', exact: true }).click();
  await page.getByRole('button', { name: 'Full calendar', exact: true }).click();
  assert.ok(await page.locator('.race-row').count() > 0);
  await page.getByRole('button', { name: 'Follow Formula 1', exact: true }).click();
  await page.reload({ waitUntil: 'networkidle' });
  await chips.getByRole('button', { name: '★ Following', exact: true }).click();
  await page.getByRole('button', { name: 'Full calendar', exact: true }).click();
  assert.ok(await page.locator('.race-row').count() > 0);
  assert.ok((await page.locator('.race-row .race-sport').allTextContents()).every(s => s === 'Formula 1'));
  await page.getByRole('searchbox').fill('a race that does not exist');
  await page.getByText('No races in this view.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Explore the calendar', exact: true }).click();
  await page.getByRole('button', { name: 'Upcoming', exact: true }).click();
  if (await page.getByRole('button', { name: 'Podium', exact: true }).count() && await page.getByRole('button', { name: 'Podium', exact: true }).isEnabled()) {
    await page.getByRole('button', { name: 'Podium', exact: true }).click();
    assert.equal(await page.getByRole('button', { name: 'Podium', exact: true }).getAttribute('aria-pressed'), 'true');
  }
  await page.getByRole('checkbox', { name: 'Forecasts ready' }).check();
  const allDrivers = page.getByRole('button', { name: /Explore all .* drivers/ });
  if (await allDrivers.count()) {
    await allDrivers.click();
    assert.ok(await page.locator('.contender-list li').count() > 5);
    await page.getByRole('button', { name: 'Show top five' }).click();
  }
  await page.getByRole('button', { name: 'Compare drivers', exact: true }).click();
  const second = page.getByLabel('Second driver');
  await second.selectOption(await second.locator('option').last().getAttribute('value'));
  assert.ok((await page.locator('.comparison-gap').innerText()).length > 20);
  const selectedRace = await page.locator('.race-focus > h3').innerText();
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.getByRole('button', { name: /Copy race link/ }).click();
  await page.getByText('Race link copied.', { exact: true }).waitFor();
  const sharedUrl = await page.evaluate(() => navigator.clipboard.readText());
  assert.ok(new URL(sharedUrl).searchParams.get('race'));
  await page.goto(sharedUrl, { waitUntil: 'networkidle' });
  assert.equal(await page.locator('.race-focus > h3').innerText(), selectedRace);
  await page.getByRole('button', { name: 'Compare drivers', exact: true }).click();
  await page.locator('.fan-coverage').scrollIntoViewIfNeeded();
  await page.waitForFunction(() => [...document.querySelectorAll('.fan-coverage .card-premium')].every(card => getComputedStyle(card.parentElement).opacity === '1'));
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${screenshots}/desktop.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('.fan-coverage').scrollIntoViewIfNeeded();
  await page.getByRole('heading', { name: 'Formula 1', exact: true }).waitFor();
  await page.screenshot({ path: `${screenshots}/mobile-series.png` });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${screenshots}/mobile.png`, fullPage: true });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'mobile must not overflow horizontally');
  await page.getByRole('button', { name: 'Results', exact: true }).click();
  assert.ok(await page.locator('.race-row').count() > 0);
  assert.equal(await page.locator('.contender-list').count(), 0, 'completed races must not display regenerated forecasts');
  await page.goto(`${url}/docs/`, { waitUntil: 'networkidle' });
  assert.ok((await page.locator('main').innerText()).length > 100);
  assert.deepEqual(errors, [], 'no browser errors or hydration errors');
  console.log(JSON.stringify({ status: 'passed', checks: ['render', 'series filter', 'follow persistence', 'search', 'empty state', 'market switch when available', 'full field', 'driver comparison', 'forecast availability filter', 'clipboard share and deep link', 'mobile overflow', 'results integrity', 'docs navigation', 'browser errors'], screenshots }, null, 2));
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
