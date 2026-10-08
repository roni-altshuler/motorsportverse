// Browser regressions for the lint repair. Serve rebuilt static exports only.
// Playback uses the committed replay; the clock controls UI time, not race data.
// No archive season is publicly available in the seven series indexes. Their
// current routes are exercised here; explicit archive fixtures live in Jest.
import { chromium } from '../projects/f1-predictions/website/node_modules/playwright/index.mjs';
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import assert from 'node:assert/strict';
import { revealRaceContent, scrollWholePage } from './qa_race_content.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = resolve(process.argv[2] || '/tmp/motorsport-lint-repair-qa');
await mkdir(output, { recursive: true });
const mime = { '.html': 'text/html', '.txt': 'text/plain', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.woff2': 'font/woff2', '.jpg': 'image/jpeg', '.ico': 'image/x-icon' };
async function serve(site) {
  const exported = resolve(root, site, 'out');
  const server = createServer(async (request, response) => {
    try {
      const path = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      let file = resolve(exported, `.${path.endsWith('/') ? `${path}index.html` : path}`);
      if (!file.startsWith(`${exported}/`)) throw new Error('invalid path');
      let bytes;
      try { bytes = await readFile(file); }
      catch {
        if (extname(file)) throw new Error('missing asset');
        try { file += '.html'; bytes = await readFile(file); }
        catch { file = resolve(exported, `.${path}/index.html`); bytes = await readFile(file); }
      }
      response.writeHead(200, { 'Content-Type': mime[extname(file)] || 'application/octet-stream' });
      response.end(bytes);
    } catch { response.writeHead(404); response.end('Not found'); }
  });
  await new Promise(done => server.listen(0, '127.0.0.1', done));
  return { server, base: `http://127.0.0.1:${server.address().port}` };
}
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', args: ['--no-sandbox'] });
const results = [];
const sizes = [['desktop', { width: 1440, height: 1000 }], ['mobile', { width: 390, height: 844 }]];
function observe(page, base) {
  const report = { pageErrors: [], consoleErrors: [], missingResources: [], failedRequests: [] };
  page.on('pageerror', e => report.pageErrors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') report.consoleErrors.push({ message: m.text(), url: m.location().url.replace(base, '') }); });
  page.on('response', r => { if (r.status() >= 400) report.missingResources.push({ url: r.url().replace(base, ''), status: r.status() }); });
  page.on('requestfailed', r => report.failedRequests.push({ url: r.url().replace(base, ''), error: r.failure()?.errorText }));
  return report;
}
async function capture(page, name, requireNoOverflow = true) {
  if (requireNoOverflow) assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name}: overflow`);
  if (name.startsWith('hub-')) {
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    for (let top = 0; top < height; top += 700) {
      await page.evaluate(top => window.scrollTo({ top, behavior: 'instant' }), top);
      await page.waitForTimeout(80);
    }
  }
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.screenshot({ path: resolve(output, `${name}.png`), fullPage: true, animations: 'disabled' });
}
function localChecks(report, site = null) {
  assert.deepEqual(report.pageErrors, []);
  const local = report.missingResources.filter(r => r.url.startsWith('/'));
  report.baselineMissingPortraits = [];
  if (site) {
    for (const resource of local) {
      if (!/^\/headshots\/[A-Z0-9_-]+\.webp$/.test(resource.url) || resource.status !== 404) continue;
      // Retain inherited portrait failures only after checking the exact base.
      // A changed build/data/script failure still fails this browser check.
      const file = `${site}/public${resource.url}`;
      const baseFile = spawnSync('git', ['cat-file', '-e', `b9408e3a56bd08e51220709aae5f017dabcda272:${file}`], { cwd: root });
      if (baseFile.status === 128 && /does not exist in/.test(baseFile.stderr.toString())) {
        report.baselineMissingPortraits.push({ ...resource, baseFile: file, baseCommit: 'b9408e3a56bd08e51220709aae5f017dabcda272' });
      }
    }
  }
  const inherited = new Set(report.baselineMissingPortraits.map(r => r.url));
  assert.deepEqual(local.filter(r => !inherited.has(r.url)), []);
}
const servers = [];
async function checkpoint() {
  await writeFile(resolve(output, 'browser-qa-in-progress.json'), `${JSON.stringify({ completed: false, browser: browser.version(), results }, null, 2)}\n`);
}
try {
  const f1 = await serve('projects/f1-predictions/website'); servers.push(f1.server);
  for (const [size, viewport] of sizes) {
    console.log(`Replay ${size}: loading committed data`);
    const context = await browser.newContext({ viewport, reducedMotion: size === 'mobile' ? 'reduce' : 'no-preference' });
    const page = await context.newPage(); const report = observe(page, f1.base);
    await page.clock.install({ time: new Date('2026-10-07T12:00:00Z') });
    await page.clock.pauseAt(new Date('2026-10-07T12:00:01Z'));
    assert.equal((await page.goto(`${f1.base}/theatre/1`, { waitUntil: 'networkidle' })).status(), 200);
    const timeline = page.getByRole('slider', { name: 'Race timeline' });
    await timeline.waitFor();
    console.log(`Replay ${size}: controls ready`);
    const value = async () => Number(await timeline.inputValue());
    if (size === 'mobile') {
      assert.equal(await page.getByRole('button', { name: 'Pause', exact: true }).count(), 0);
      assert.equal(await value(), 0);
      await page.clock.runFor(1000); assert.equal(await value(), 0);
      await page.getByRole('button', { name: /^Play the .* race replay$/ }).click();
    }
    await page.getByRole('button', { name: 'Pause', exact: true }).click();
    await page.clock.runFor(200);
    const paused = await value();
    console.log(`Replay ${size}: paused`);
    await page.clock.runFor(500); assert.equal(await value(), paused);
    await page.getByRole('button', { name: '1×', exact: true }).click();
    await page.getByRole('button', { name: 'Play', exact: true }).click();
    await page.clock.runFor(1000);
    const first = await value(); assert.ok(first - paused > .8 && first - paused < 1.2, `1× ${first - paused}`);
    await page.getByRole('button', { name: '4×', exact: true }).click();
    await page.clock.runFor(1000);
    const fast = await value(); assert.ok(fast - first > 3.7 && fast - first < 4.3, `4× ${fast - first}`);
    await page.getByRole('button', { name: 'Pause', exact: true }).click();
    await page.clock.runFor(200); const stopped = await value();
    await page.clock.runFor(500); assert.equal(await value(), stopped);
    for (const speed of ['8×', '2×', '1×']) {
      await page.getByRole('button', { name: speed, exact: true }).click();
      await page.getByRole('button', { name: 'Play', exact: true }).click();
      await page.clock.runFor(200);
      await page.getByRole('button', { name: 'Pause', exact: true }).click();
      await page.clock.runFor(100);
    }
    const stage = page.getByRole('group', { name: /^Race replay player/ });
    await stage.focus(); const beforeSeek = await value();
    await page.keyboard.press('ArrowRight'); assert.ok(Math.abs(await value() - beforeSeek - 5) < .01);
    await page.keyboard.press('ArrowLeft'); assert.ok(Math.abs(await value() - beforeSeek) < .01);
    await page.keyboard.press('Space'); await page.getByRole('button', { name: 'Pause', exact: true }).waitFor();
    await page.keyboard.press('Space'); await page.getByRole('button', { name: 'Play', exact: true }).waitFor();
    // Seek into the real stored race so focus can visibly dim the other cars.
    await timeline.focus(); await page.keyboard.press('Home');
    for (let i = 0; i < 240; i++) await page.keyboard.press('ArrowRight');
    assert.equal(await value(), 120); await page.clock.runFor(200);
    const canvasHash = async () => createHash('sha256').update(await page.locator('canvas').evaluate(c => c.toDataURL())).digest('hex');
    const beforeFocus = await canvasHash();
    const norris = page.getByRole('button').filter({ hasText: /NOR.*Norris/ });
    await norris.click(); await page.clock.runFor(100);
    const focused = await canvasHash(); assert.notEqual(focused, beforeFocus);
    await capture(page, `replay-${size}`);
    await norris.click(); await page.clock.runFor(100); assert.equal(await canvasHash(), beforeFocus);
    await page.getByRole('button', { name: /Restart/ }).click();
    assert.equal(await value(), 0); await page.clock.runFor(500); assert.ok(await value() > .3);
    await page.getByRole('button', { name: 'Pause', exact: true }).click();
    localChecks(report);
    results.push({ feature: 'replay controls', viewport: size, raceData: 'committed 2026 round_01 replay', injectedRaceData: false, flows: ['pause remains stable', '1× and 4× measured UI timing', 'repeated controls', 'keyboard space / ±5s seek', 'scrub to 120s', 'focus redraw and restore', 'restart'], mobileReducedMotionGate: size === 'mobile', canvasHashes: { beforeFocus, focused }, ...report });
    await checkpoint();
    await context.close();
    console.log(`Replay ${size}: passed`);
  }
  const hub = await serve('website'); servers.push(hub.server);
  for (const [size, viewport] of sizes) {
    console.log(`Hub ${size}: loading actual race feed`);
    const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
    const page = await context.newPage(); const report = observe(page, hub.base);
    await page.clock.setFixedTime(new Date('2026-10-07T12:00:00Z'));
    await page.goto(`${hub.base}/?race=f1-predictions-2026-1#race-centre`, { waitUntil: 'networkidle' });
    const centre = page.locator('#race-centre');
    await centre.getByRole('heading', { name: 'Australian Grand Prix' }).waitFor();
    assert.equal(await centre.getByRole('button', { name: 'Results', exact: true }).getAttribute('aria-pressed'), 'true');
    await centre.getByRole('button', { name: 'Follow Formula 1', exact: true }).click();
    await page.reload({ waitUntil: 'networkidle' });
    await centre.getByRole('button', { name: 'Unfollow Formula 1' }).waitFor();
    await centre.getByRole('button', { name: '★ Following', exact: true }).click();
    assert.ok(await centre.locator('.race-row').count() > 0);
    await centre.getByRole('searchbox').fill('does not match a race');
    await centre.getByText('No races in this view.', { exact: true }).waitFor();
    await page.evaluate(() => {
      history.pushState({}, '', '/?race=f1-predictions-2026-1#race-centre');
      dispatchEvent(new PopStateEvent('popstate'));
    });
    await centre.getByRole('heading', { name: 'Australian Grand Prix' }).waitFor();
    assert.equal(await centre.getByRole('searchbox').inputValue(), '');
    await capture(page, `hub-${size}`);
    // Keyboard filtering retains first-match selection after an existing arrow selection.
    await page.evaluate(() => document.activeElement?.blur());
    await page.keyboard.press('Control+k');
    const dialog = page.getByRole('dialog', { name: 'Command palette' });
    const search = dialog.getByRole('textbox', { name: 'Search', exact: true });
    await search.waitFor(); await search.focus();
    await page.keyboard.press('ArrowDown'); await page.keyboard.press('ArrowDown');
    await search.fill('Formula');
    assert.equal(await dialog.getByRole('option').first().getAttribute('aria-selected'), 'true');
    await page.keyboard.press('Escape'); assert.equal(await dialog.count(), 0);
    await page.keyboard.press('Control+k'); await search.waitFor(); assert.equal(await search.inputValue(), '');
    await search.fill('Documentation'); await page.keyboard.press('Enter');
    await page.waitForURL(/\/docs\/?$/); await page.goBack({ waitUntil: 'networkidle' });
    // Browser day must win over the static build day even on a much later visit.
    await page.clock.setFixedTime(new Date('2030-01-01T12:00:00Z'));
    await page.goto(hub.base, { waitUntil: 'networkidle' });
    await centre.getByText('No races in this view.', { exact: true }).waitFor();
    assert.equal(await centre.locator('.race-count strong').innerText(), '0');
    await centre.getByRole('button', { name: 'Full calendar', exact: true }).click();
    assert.ok(await centre.locator('.race-row').count() > 0);
    localChecks(report);
    results.push({ feature: 'hub state and command palette', viewport: size, injectedRaceData: false, clockOnly: ['2026-10-07', '2030-01-01'], flows: ['completed race deep link', 'stored favourites / following after reload', 'search / popstate reset', 'keyboard search selection / close / reopen / navigation', 'browser UTC day replaces static snapshot'], ...report });
    await checkpoint();
    await context.close();
    console.log(`Hub ${size}: passed`);
  }
  for (const code of ['f2', 'f3', 'formula-e', 'indycar', 'motogp', 'nascar', 'wrc']) {
    console.log(`Race detail ${code}: current season`);
    const site = `projects/${code}-predictions/website`;
    const index = JSON.parse(await readFile(resolve(root, site, 'public/data/seasons.json'), 'utf8'));
    assert.deepEqual(index.available, [2026]);
    const round = JSON.parse(await readFile(resolve(root, site, 'public/data/rounds/round_01.json'), 'utf8'));
    const headline = ['indycar', 'nascar'].includes(code) ? round.raceName || round.venueName : round.venueName;
    const served = await serve(site); servers.push(served.server);
    for (const [size, viewport] of sizes) {
      const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
      const page = await context.newPage(); const report = observe(page, served.base);
      assert.equal((await page.goto(`${served.base}/race/1/`, { waitUntil: 'networkidle' })).status(), 200);
      await page.getByRole('main').getByRole('heading').filter({ hasText: headline }).first().waitFor();
      assert.ok(/Result \+ Forecast/i.test(await page.getByRole('main').innerText()), `${code}/${size}: classification status missing`);
      report.viewportWidth = viewport.width;
      report.documentWidth = await page.evaluate(() => document.documentElement.scrollWidth);
      report.horizontalOverflow = report.documentWidth > viewport.width;
      if (code === 'motogp') {
        report.raceContent = await revealRaceContent(page, round);
        report.scrollStops = await scrollWholePage(page);
      }
      // Record all series layout findings; this lint patch changes no markup or
      // CSS. Replay/hub control flows still require no horizontal overflow.
      await capture(page, `${code}-${size}`, false);
      localChecks(report, site);
      results.push({ feature: 'current season race detail', series: code, viewport: size, availableSeasons: index.available, archiveBrowserFlow: 'not available; explicit archive fixtures tested in F2 Jest', injectedRaceData: false, round: 1, venue: round.venueName, ...report });
      await checkpoint();
      await context.close();
    }
  }
  await writeFile(resolve(output, 'browser-qa.json'), `${JSON.stringify({ browser: browser.version(), results }, null, 2)}\n`);
  console.log(JSON.stringify({ output, flows: results.length, pageErrors: results.flatMap(r => r.pageErrors).length }));
} finally {
  await browser.close();
  await Promise.all(servers.map(server => new Promise(done => server.close(done))));
}
