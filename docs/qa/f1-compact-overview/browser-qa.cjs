const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const site = path.join(root, 'projects/f1-predictions/website');
const { chromium } = require(require.resolve('playwright', { paths: [site] }));
const base = process.argv[2] || 'http://127.0.0.1:3361';
const mode = process.argv[3] || 'development';
const output = __dirname;
const report = { mode, base, browser: 'Chromium', sourceBase: 'fd1f6104939665dc1e807e6ce1ea484f82b11afc', cases: [] };
fs.mkdirSync(path.join(output, 'screenshots'), { recursive: true });
let browser;

(async () => {
  browser = await chromium.launch({ executablePath: '/usr/bin/chromium', headless: true });
  report.browserVersion = browser.version();
  async function run(name, viewport, action) {
    const page = await browser.newPage({ viewport, reducedMotion: 'no-preference' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    try {
      const details = await action(page);
      const width = await page.evaluate(() => document.documentElement.scrollWidth);
      assert(width <= viewport.width + 1, `${name}: horizontal document overflow`);
      assert.deepEqual(errors, [], `${name}: page errors`);
      report.cases.push({ name, viewport, passed: true, errors, scrollWidth: width, ...details });
    } finally { await page.close(); }
  }
  const mobile = { width: 390, height: 844 };
  const desktop = { width: 1440, height: 900 };
  for (const [name, viewport] of [['desktop', desktop], ['mobile', mobile], ['narrow', { width: 320, height: 780 }]]) {
    await run(`overview-${name}`, viewport, async page => {
      await page.goto(`${base}/race/17`, { waitUntil: 'networkidle' });
      await page.getByRole('list', { name: 'Observed race leaders' }).waitFor();
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(350);
      const overview = page.getByRole('region', { name: 'Race overview' });
      assert.match(await overview.innerText(), /Antonelli/);
      assert.match(await overview.innerText(), /Withheld/);
      assert.match(await overview.innerText(), /Pre-race grid order/);
      assert.equal(await page.locator('details[open]').count(), 0);
      assert.equal(await page.locator('main canvas').count(), 0);
      const leaders = await page.getByRole('list', { name: 'Observed race leaders' }).boundingBox();
      assert(leaders.y < viewport.height, 'Observed leaders must start in the first viewport');
      await page.screenshot({ path: path.join(output, 'screenshots', `${mode}-${name}.png`) });
      const baseline = page.locator('summary').filter({ hasText: 'Baseline pick and sources' });
      await baseline.focus();
      for (let i = 0; i < 3; i++) {
        await page.keyboard.press('Enter');
        assert.equal(await baseline.evaluate(node => node.parentElement.open), true);
        assert.match(await page.getByRole('region', { name: 'Official-grid baseline' }).innerText(), /06:53:07 UTC/);
        await page.keyboard.press('Space');
        assert.equal(await baseline.evaluate(node => node.parentElement.open), false);
      }
      const hold = page.locator('summary').filter({ hasText: 'Forecast hold and event record' });
      await hold.focus();
      const outline = await hold.evaluate(node => ({ width: getComputedStyle(node).outlineWidth, style: getComputedStyle(node).outlineStyle }));
      assert(parseFloat(outline.width) > 0 && outline.style !== 'none', 'Keyboard focus must be visible');
      await page.keyboard.press('Enter');
      assert.match(await page.getByRole('complementary', { name: 'Publication review' }).innerText(), /Withdrawn · excluded from accuracy/);
      await page.keyboard.press('Space');
      await page.getByRole('link', { name: 'Full race result →', exact: true }).click();
      await page.waitForTimeout(150);
      assert.match(page.url(), /#grandPrix$/);
      const heading = await page.getByRole('heading', { name: 'Grand Prix Result', exact: true }).boundingBox();
      assert(heading.y >= 120 && heading.y < viewport.height, 'Result heading must remain below sticky navigation');
      return { observedLeadersTop: leaders.y, keyboardToggleCycles: 3, focus: outline, fullResultAnchorHeadingTop: heading.y };
    });
  }
  await run('intentional-profile-and-circuit-navigation', desktop, async page => {
    await page.goto(`${base}/race/17`, { waitUntil: 'networkidle' });
    await page.getByRole('list', { name: 'Observed race leaders' }).getByRole('link', { name: 'Max Verstappen', exact: true }).click();
    await page.waitForURL('**/driver/VER');
    await page.locator('h1').filter({ hasText: 'Max Verstappen' }).waitFor();
    await page.goBack();
    await page.getByRole('list', { name: 'Observed race leaders' }).waitFor();
    await page.getByRole('link', { name: 'Explore Circuit →', exact: true }).click();
    await page.waitForURL('**/circuits');
    await page.locator('h1').waitFor();
    await page.goBack();
    await page.getByRole('list', { name: 'Observed race leaders' }).waitFor();
    assert.match(await page.getByRole('region', { name: 'Race overview' }).innerText(), /Withheld/);
    return { driverProfile: '/driver/VER', circuitWorkspace: '/circuits', backNavigation: true };
  });
  await run('interrupted-and-repeated-race-navigation', desktop, async page => {
    let delayed = false;
    await page.route('**/data/rounds/round_16.json', async route => {
      delayed = true;
      await new Promise(resolve => setTimeout(resolve, 2000));
      try { await route.continue(); } catch { /* Leaving the route can cancel this request. */ }
    });
    await page.goto(`${base}/calendar`, { waitUntil: 'networkidle' });
    await page.locator('main a[href="/race/16"]').first().click();
    await page.getByRole('region', { name: 'Forecast data availability' }).waitFor();
    assert.equal(await page.getByRole('list', { name: 'Observed race leaders' }).count(), 0);
    await page.goBack();
    await page.locator('main a[href="/race/17"]').first().click();
    await page.getByRole('list', { name: 'Observed race leaders' }).waitFor();
    await page.waitForTimeout(2300);
    assert.equal(delayed, true);
    assert.match(await page.getByRole('region', { name: 'Race overview' }).innerText(), /1:42:00\.785/);
    for (let i = 0; i < 2; i++) {
      await page.getByRole('link', { name: '← Season calendar', exact: true }).click();
      await page.locator('main a[href="/race/16"]').first().click();
      await page.getByText('No pre-race model forecast recorded.', { exact: true }).waitFor();
      await page.getByRole('link', { name: '← Season calendar', exact: true }).click();
      await page.locator('main a[href="/race/17"]').first().click();
      await page.getByRole('list', { name: 'Observed race leaders' }).waitFor();
      assert.match(await page.getByRole('region', { name: 'Race overview' }).innerText(), /Withheld/);
      assert.equal(await page.locator('details[open]').count(), 0);
    }
    return { delayedRound16: true, lateResponseDidNotReplaceRound17: true, repeatedCycles: 2 };
  });
  await run('loading-round-data', mobile, async page => {
    await page.route('**/data/rounds/round_17.json', async route => {
      await new Promise(resolve => setTimeout(resolve, 1500));
      await route.continue();
    });
    await page.goto(`${base}/race/17`, { waitUntil: 'domcontentloaded' });
    await page.getByText('Checking race data', { exact: true }).waitFor();
    assert.equal(await page.getByRole('list', { name: 'Observed race leaders' }).count(), 0);
    await page.screenshot({ path: path.join(output, 'screenshots', `${mode}-loading.png`) });
    await page.getByRole('list', { name: 'Observed race leaders' }).waitFor();
    return { simulatedDelayMs: 1500, resultsHiddenUntilChecked: true, recovered: true };
  });
  for (const [name, status, body] of [['http-error', 404, '{}'], ['invalid-json', 200, 'not JSON']]) {
    await run(name, mobile, async page => {
      await page.route('**/data/rounds/round_17.json', route => route.fulfill({ status, contentType: 'application/json', body }));
      await page.goto(`${base}/race/17`, { waitUntil: 'networkidle' });
      await page.getByText('Race data unavailable', { exact: true }).waitFor();
      assert.equal(await page.getByRole('list', { name: 'Observed race leaders' }).count(), 0);
      assert.equal(await page.getByRole('region', { name: 'Official-grid baseline' }).count(), 0);
      await page.screenshot({ path: path.join(output, 'screenshots', `${mode}-${name}.png`) });
      await page.unroute('**/data/rounds/round_17.json');
      await page.reload({ waitUntil: 'networkidle' });
      await page.getByRole('list', { name: 'Observed race leaders' }).waitFor();
      return { simulatedResponseStatus: status, verifiedStatusNotInferred: true, refreshRecovered: true };
    });
  }
  await run('historical-no-result-snapshot', mobile, async page => {
    const fixture = path.join(site, 'src/__tests__/fixtures/publication-hold/singapore-no-result.json');
    await page.route('**/data/rounds/round_17.json', route => route.fulfill({ status: 200, contentType: 'application/json', body: fs.readFileSync(fixture, 'utf8') }));
    await page.goto(`${base}/race/17`, { waitUntil: 'networkidle' });
    await page.getByText('No race classification is recorded in this round yet.', { exact: true }).waitFor();
    assert.equal(await page.getByRole('list', { name: 'Observed race leaders' }).count(), 0);
    assert.match(await page.getByRole('region', { name: 'Race overview' }).innerText(), /Withheld/);
    assert.match(await page.getByRole('region', { name: 'Race overview' }).innerText(), /Pre-race grid order/);
    await page.screenshot({ path: path.join(output, 'screenshots', `${mode}-historical-no-result.png`) });
    return { source: 'Existing immutable pre-result fixture; not current availability', baselineNotPresentedAsResult: true };
  });
  await run('off-calendar-round', mobile, async page => {
    await page.goto(`${base}/race/24`, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: 'Race Not Found', exact: true }).waitFor();
    assert.equal(await page.getByRole('region', { name: 'Race overview' }).count(), 0);
    return { offCalendarRound: 24, inventedEventOrForecast: false };
  });
  await browser.close();
  report.checkedAt = new Date().toISOString();
  fs.writeFileSync(path.join(output, `${mode}-qa.json`), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ mode, cases: report.cases.length, failed: report.cases.filter(c => !c.passed).length }));
})().catch(async error => {
  console.error(error);
  if (browser) await browser.close();
  process.exitCode = 1;
});
