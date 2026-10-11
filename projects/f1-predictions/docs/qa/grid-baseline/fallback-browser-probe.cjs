// Run against a local production export; faults affect only intercepted browser responses.
const path = require('node:path');
const websiteRoot = path.resolve(__dirname, '../../../website');
const { chromium } = require(require.resolve('playwright', { paths: [websiteRoot] }));
const fs = require('fs');
const crypto = require('crypto');
const dir = process.env.QA_OUTPUT_DIR || path.join(require('node:os').tmpdir(), 'motorsportverse-grid-baseline/fallback-corrected-evidence');
const sourcePath = path.join(websiteRoot, 'public/data/rounds/round_17.json');
const original = fs.readFileSync(sourcePath);
const source = JSON.parse(original);
const origin = process.env.QA_ORIGIN || 'http://127.0.0.1:8090', prefix = '/motorsportverse/projects/f1';
fs.mkdirSync(dir, { recursive: true });
async function state(page) {
  const text = await page.locator('body').innerText();
  return {
    baselineVisible: await page.getByRole('region', { name: 'Official-grid baseline', exact: true }).count() > 0,
    publicationNoticeVisible: await page.getByRole('complementary', { name: 'Publication review' }).count() > 0,
    modelWithheldCopyVisible: /Forecast withheld/i.test(text),
    modelForecastHeadingVisible: await page.getByRole('heading', { name: /Predicted Podium|Predicted Classification/i }).count() > 0,
    loadingRaceData: await page.getByLabel('Loading race data').count() > 0 || /Loading race data/i.test(text),
    availabilityNoticeVisible: await page.getByRole('region', { name: 'Forecast data availability', exact: true }).count() > 0,
    forecastStatusUnverifiable: /Forecast status cannot currently be verified/i.test(text),
    loadingCopyVisible: /This round.s data is still loading/i.test(text),
    unavailableCopyVisible: /This round.s data could not be loaded/i.test(text),
    automaticPublicationClaim: /not published predictions yet|Once the workflow runs|will automatically appear/i.test(text),
    unavailableCopy: text.match(/.{0,50}(not published predictions yet|workflow runs|forecast is withheld|data unavailable).{0,130}/gi),
    title: await page.title(),
  };
}
function assertHidden(snapshot) {
  if (snapshot.baselineVisible || snapshot.modelForecastHeadingVisible) throw Error('Unavailable inputs exposed a baseline or model forecast: ' + JSON.stringify(snapshot));
}
(async () => {
  const browser = await chromium.launch({ executablePath: '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
  const checks = [];
  for (const width of [1440, 390]) for (const path of ['/', '/race/17']) for (const fault of ['slow-round', 'missing-round', 'changed-grid', 'missing-grid']) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    await page.clock.install({ time: new Date('2026-10-11T07:50:00Z') });
    const errors = [], failures = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('response', r => { if (r.url().startsWith(origin) && r.status() >= 400) failures.push({ url: r.url(), status: r.status() }); });
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    let firstRequest;
    const requested = new Promise(resolve => { firstRequest = resolve; });
    let intercepted = 0;
    await page.route('**/data/rounds/round_17.json', async route => {
      intercepted++;
      firstRequest();
      if (fault === 'slow-round') { await gate; await route.continue(); return; }
      if (fault === 'missing-round') { await route.fulfill({ status: 404, contentType: 'application/json', body: '{"error":"QA missing round response"}' }); return; }
      const changed = JSON.parse(original);
      if (fault === 'missing-grid') changed.weekendResults.sessions = changed.weekendResults.sessions.filter(s => s.key !== 'startingGrid');
      else {
        const grid = changed.weekendResults.sessions.find(s => s.key === 'startingGrid');
        const first = grid.rows.find(r => r.position === 1), second = grid.rows.find(r => r.position === 2);
        [first.position, second.position] = [second.position, first.position];
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(changed) });
    });
    await page.goto(origin + prefix + path, { waitUntil: 'domcontentloaded' });
    await Promise.race([requested, new Promise((_, reject) => setTimeout(() => reject(Error('Round request not intercepted')), 15000))]);
    const result = { width, path, fault };
    if (fault === 'slow-round') {
      await page.waitForTimeout(700);
      result.pending = await state(page);
      assertHidden(result.pending);
      if (!result.pending.availabilityNoticeVisible || !result.pending.forecastStatusUnverifiable || !result.pending.loadingCopyVisible || result.pending.automaticPublicationClaim) throw Error('Pending request makes a false publication claim');
      await page.getByRole('region', { name: 'Forecast data availability' }).screenshot({ path: `${dir}/${path === '/' ? 'home' : 'race17'}-slow-${width}.png` });
      release();
      await page.getByRole('region', { name: 'Official-grid baseline' }).waitFor();
      await page.getByRole('complementary', { name: 'Publication review' }).waitFor();
      result.resolved = await state(page);
      if (!result.resolved.baselineVisible || !result.resolved.modelWithheldCopyVisible || result.resolved.modelForecastHeadingVisible) throw Error('Resolved slow data bypassed the hold');
    } else {
      if (fault === 'missing-round') {
        await page.waitForTimeout(900);
        await page.getByText('Race data unavailable', { exact: true }).waitFor();
      } else await page.getByRole('complementary', { name: 'Publication review' }).waitFor();
      await page.clock.runFor(800);
      result.fallback = await state(page);
      assertHidden(result.fallback);
      if (fault === 'missing-round' && (!result.fallback.availabilityNoticeVisible || !result.fallback.forecastStatusUnverifiable || !result.fallback.unavailableCopyVisible || result.fallback.automaticPublicationClaim)) throw Error('Missing request makes a false publication claim');
      if (fault !== 'missing-round' && (!result.fallback.publicationNoticeVisible || !result.fallback.modelWithheldCopyVisible)) throw Error('Grid fallback removed the model hold');
      if (fault === 'missing-grid' && await page.getByRole('table', { name: 'Starting grid · after penalties' }).count()) throw Error('Missing grid still rendered');
      const region = fault === 'missing-round'
        ? page.getByRole('region', { name: 'Forecast data availability' })
        : page.getByRole('complementary', { name: 'Publication review' });
      await region.screenshot({ path: `${dir}/${path === '/' ? 'home' : 'race17'}-${fault}-${width}.png` });
    }
    result.interceptedRequests = intercepted;
    result.pageErrors = errors;
    result.httpFailures = failures;
    if (errors.length) throw Error(errors.join('\n'));
    if (failures.some(r => fault !== 'missing-round' || r.status !== 404 || !r.url.endsWith('/rounds/round_17.json'))) throw Error('Unexpected local HTTP failure');
    checks.push(result);
    await context.close();
  }
  await browser.close();
  if (!fs.readFileSync(sourcePath).equals(original)) throw Error('Repository source bytes changed');
  const root = websiteRoot + '/';
  const artifactSha256 = crypto.createHash('sha256').update(fs.readFileSync(root + 'public/data/baselines/2026_round_17_f994d9796f18.json')).digest('hex');
  const receiptSha256 = crypto.createHash('sha256').update(fs.readFileSync(root + 'public/data/baselines/2026_round_17.json')).digest('hex');
  if (artifactSha256 !== 'f994d9796f18458398c2733e48ab27a984cff51aa57874323d1aa61f6cde0c58' || receiptSha256 !== '820d047210b86da6dd0a95bdf774cfca7fccfbb37daefbed64f6a76eeeacac51') throw Error('Immutable baseline record changed');
  const sourceHashes = Object.fromEntries(['src/components/HomePage.tsx','src/components/RaceDetailPage.tsx','src/components/race-detail/RoundDataStatus.tsx','src/lib/useRoundArtifact.ts'].map(path => [path, crypto.createHash('sha256').update(fs.readFileSync(root + path)).digest('hex')]));
  const report = { checkedAt: new Date().toISOString(), reviewedBaseHead: 'efcff5294c8e08079a827da4d6747b0fa83822a0', testedSourceHashes: sourceHashes, browser: 'Chromium', frozenClock: '2026-10-11T07:50:00Z', artifactSha256, receiptSha256, roundSourceSha256: crypto.createHash('sha256').update(original).digest('hex'), sourcePublicationHoldUnchanged: source.publicationHold, faultInjectionOnly: true, sourceDataChanges: false, independentSeasonLevelHoldAvailable: false, checks };
  fs.writeFileSync(dir + '/report.json', JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ cases: checks.length, pageErrors: checks.flatMap(c => c.pageErrors), missingRoundStates: checks.filter(c => c.fault === 'missing-round').map(c => ({ width: c.width, path: c.path, ...c.fallback })) }));
})().catch(e => { console.error(e); process.exit(1); });
