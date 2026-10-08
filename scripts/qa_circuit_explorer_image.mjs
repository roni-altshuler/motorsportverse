// Local controlled checkerboard fixtures only. This does not approve a circuit map.
import { chromium } from '../projects/f1-predictions/website/node_modules/playwright/index.mjs';
import { build } from '../projects/f1-predictions/website/node_modules/esbuild/lib/main.js';
import { createServer } from 'node:http';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const root = fileURLToPath(new URL('../', import.meta.url));
const site = resolve(root, 'projects/f1-predictions/website');
const output = resolve(process.argv[2] || '/tmp/motorsport-explorer-image-browser');
await mkdir(output, { recursive: true });
const fixture = JSON.parse(execFileSync(resolve(site, 'node_modules/.bin/tsx'), ['-e', 'import { schematic, review, pngBase64 } from "./src/test-support/circuitExplorer"; process.stdout.write(JSON.stringify({ schematic, review, pngBase64 }));'], { cwd: site, encoding: 'utf8' }));
const png = Buffer.from(fixture.pngBase64, 'base64');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const palettes = await Promise.all(['f1', 'f2', 'f3', 'formula-e', 'nascar', 'indycar', 'motogp', 'wrc', 'wec', 'imsa', 'hub'].map(async name => {
  const directory = name === 'hub' ? resolve(root, 'website') : resolve(root, `projects/${name}-predictions/website`);
  const css = await readFile(resolve(directory, 'src/styles/tokens.css'), 'utf8');
  for (const token of ['ink', 'canvas']) assert.match(css, new RegExp(`--${token}:\\s*#[0-9a-f]{6}`, 'i'), `${name}: supported ${token} token`);
  return { name, css };
}));
function contrast(first, second) {
  const luminance = color => {
    const rgb = color.match(/^rgb\((\d+), (\d+), (\d+)\)$/);
    assert.ok(rgb, `expected opaque computed color: ${color}`);
    const values = rgb.slice(1).map(value => {
      const channel = Number(value) / 255;
      return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
    });
    return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
  };
  const values = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}
async function selectedStyles(page) {
  return page.evaluate(() => {
    const root = document.querySelector('section[aria-label="QA venue circuit explorer"]');
    const paintedBackground = element => {
      for (let current = element; current; current = current.parentElement) {
        const color = getComputedStyle(current).backgroundColor;
        if (color !== 'rgba(0, 0, 0, 0)') return color;
      }
      throw new Error('No opaque background');
    };
    const tokenColor = token => {
      const probe = document.createElement('span'); probe.style.color = `var(--${token})`; root.append(probe);
      const color = getComputedStyle(probe).color; probe.remove(); return color;
    };
    const marker = root.querySelector('button[aria-label^="Show Turn"][aria-pressed="true"] span');
    const otherMarker = root.querySelector('button[aria-label^="Show Turn"][aria-pressed="false"] span');
    const list = root.querySelector('ol button[aria-pressed="true"]');
    const otherList = root.querySelector('ol button[aria-pressed="false"]');
    const header = root.querySelector('button[aria-expanded]');
    const focused = root.querySelector('button:focus-visible');
    if (!focused) throw new Error('Expected keyboard focus-visible');
    const focus = getComputedStyle(focused);
    return {
      ink: tokenColor('ink'), canvas: tokenColor('canvas'),
      glyph: getComputedStyle(header.querySelector('[aria-hidden]')).color, headerBackground: paintedBackground(header),
      markerBackground: getComputedStyle(marker).backgroundColor, markerForeground: getComputedStyle(marker).color,
      otherMarkerBackground: getComputedStyle(otherMarker).backgroundColor,
      listBorder: getComputedStyle(list).borderTopColor, listBackground: paintedBackground(list),
      otherListBorder: getComputedStyle(otherList).borderTopColor,
      focus: { name: focused.getAttribute('aria-label') || focused.textContent, color: focus.outlineColor, width: focus.outlineWidth, style: focus.outlineStyle, offset: focus.outlineOffset, background: paintedBackground(focused) },
    };
  });
}
function assertSelectedContrast(styles, label) {
  const ratios = {
    glyph: contrast(styles.glyph, styles.headerBackground),
    markerText: contrast(styles.markerForeground, styles.markerBackground),
    markerSelection: contrast(styles.markerBackground, styles.otherMarkerBackground),
    listBorder: contrast(styles.listBorder, styles.listBackground),
    listSelection: contrast(styles.listBorder, styles.otherListBorder),
    keyboardFocus: contrast(styles.focus.color, styles.focus.background),
  };
  for (const [name, ratio] of Object.entries(ratios)) assert.ok(ratio >= (['glyph', 'markerText'].includes(name) ? 4.5 : 3), `${label}: ${name} contrast ${ratio.toFixed(2)}:1`);
  assert.equal(styles.markerBackground, styles.ink); assert.equal(styles.markerForeground, styles.canvas);
  assert.equal(styles.listBorder, styles.ink); assert.equal(styles.focus.color, styles.ink);
  assert.ok(parseFloat(styles.focus.width) >= 2, `${label}: focus outline ${JSON.stringify(styles.focus)}`); assert.equal(styles.focus.style, 'solid');
  return { styles, ratios };
}
const modes = ['valid', 'hash-mismatch', 'dimensions', 'corrupt', 'missing', 'retry', 'reopen', 'render-error', 'decode-delay', 'cancel-decode'];
const configs = {}, requests = {};
for (const mode of modes) for (const size of ['desktop', 'mobile']) {
  const id = `${mode}-${size}`, manifest = structuredClone(fixture.schematic);
  let bytes = png;
  if (mode === 'hash-mismatch') { bytes = Buffer.from(png); bytes[bytes.length - 1] ^= 1; }
  if (mode === 'dimensions') { manifest.asset.width = 13; manifest.source.width = 130; }
  if (mode === 'corrupt') { bytes = png.subarray(0, 16); manifest.asset.bytes = bytes.length; manifest.asset.sha256 = hash(bytes); }
  const body = JSON.stringify(manifest);
  configs[id] = { mode, body, bytes, review: { ...fixture.review, assetSha256: manifest.asset.sha256, manifestSha256: hash(body) } };
  requests[id] = { manifests: 0, images: 0 };
}
await build({ stdin: {
  contents: `import React from ${JSON.stringify(resolve(site, 'node_modules/react/index.js'))};
import { createRoot } from ${JSON.stringify(resolve(site, 'node_modules/react-dom/client.js'))};
import CircuitExplorer from ${JSON.stringify(resolve(site, 'src/components/ui/CircuitExplorer.tsx'))};
const id = location.pathname.split('/')[2];
fetch('/case/'+id+'/config.json').then(r=>r.json()).then(review=>{
 const root=createRoot(document.getElementById('root'));
 window.unmountExplorer=()=>root.unmount();
 root.render(<CircuitExplorer review={review} basePath={'/case/'+id} />);
});`,
  resolveDir: site, loader: 'jsx',
}, outfile: resolve(output, 'bundle.js'), bundle: true, platform: 'browser', jsx: 'automatic', tsconfig: resolve(site, 'tsconfig.json'), nodePaths: [resolve(site, 'node_modules')], define: { 'process.env.NODE_ENV': '"production"' } });
const bundle = await readFile(resolve(output, 'bundle.js'));
// Use the already-built F1 styles without registering a test review on a product page.
const staticAssets = new Map();
for (const directory of ['css', 'media']) {
  const base = resolve(site, 'out/_next/static', directory);
  for (const name of await readdir(base)) {
    if (!/\.(css|woff2)$/.test(name)) continue;
    staticAssets.set(`/_next/static/${directory}/${name}`, await readFile(resolve(base, name)));
  }
}
const cssLinks = [...staticAssets.keys()].filter(path => path.endsWith('.css')).map(path => `<link rel="stylesheet" href="${path}">`).join('');
const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">${cssLinks}<style>body{margin:24px;background:#000;color:white;font-family:Arial}#root{max-width:1100px;margin-top:24px}.qa-title{font-size:28px;font-weight:bold;margin-bottom:12px}.qa-notice{max-width:640px;color:#ccc}</style></head><body><h1 class="qa-title">Controlled image integrity QA</h1><p class="qa-notice">Synthetic checkerboard fixture. No approved production map.</p><div id="root"></div><script src="bundle.js"></script></body></html>`;
const server = createServer((request, response) => {
  const path = new URL(request.url, 'http://localhost').pathname;
  if (path === '/favicon.ico') { response.writeHead(204); response.end(); return; }
  if (staticAssets.has(path)) { response.setHeader('Content-Type', path.endsWith('.css') ? 'text/css' : 'font/woff2'); response.end(staticAssets.get(path)); return; }
  const id = path.split('/')[2], config = configs[id];
  if (!config) { response.writeHead(404); response.end(); return; }
  if (path.endsWith('/bundle.js')) { response.setHeader('Content-Type', 'text/javascript'); response.end(bundle); }
  else if (path.endsWith('/config.json')) { response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify(config.review)); }
  else if (path.endsWith('/manifest.json')) { requests[id].manifests++; response.setHeader('Content-Type', 'application/json'); response.end(config.body); }
  else if (path.endsWith('/map.png')) {
    requests[id].images++;
    if (config.mode === 'missing' || (['retry', 'reopen'].includes(config.mode) && requests[id].images === 1)) { response.writeHead(404); response.end(); }
    else { response.setHeader('Content-Type', 'image/png'); response.end(config.bytes); }
  } else { response.setHeader('Content-Type', 'text/html'); response.end(html); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const url = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ executablePath: '/usr/bin/chromium', args: ['--no-sandbox'] });
const results = [];
try {
  for (const mode of modes) for (const [size, viewport] of [['desktop', { width: 1440, height: 1000 }], ['mobile', { width: 390, height: 844 }]]) {
    const id = `${mode}-${size}`, context = await browser.newContext({ viewport, reducedMotion: 'no-preference' });
    await context.addInitScript(() => {
      window.imageUrls = { created: [], revoked: [] };
      const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL);
      URL.createObjectURL = blob => { const url = create(blob); window.imageUrls.created.push(url); return url; };
      URL.revokeObjectURL = url => { window.imageUrls.revoked.push(url); revoke(url); };
      if (/decode-delay|cancel-decode/.test(location.pathname)) {
        const native = HTMLImageElement.prototype.decode;
        const gate = new Promise(resolve => { window.finishDecode = resolve; });
        HTMLImageElement.prototype.decode = async function () { await native.call(this); await gate; };
      }
    });
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push({ kind: 'pageerror', message: error.message }));
    page.on('console', message => { if (message.type() === 'error') errors.push({ kind: 'console', message: message.text() }); });
    await page.goto(`${url}/case/${id}/`, { waitUntil: 'networkidle' });
    const launch = page.getByRole('button', { name: /Explore QA venue/ });
    await launch.waitFor(); assert.equal(requests[id].manifests + requests[id].images, 0);
    let collapsedGlyph;
    if (mode === 'valid') {
      collapsedGlyph = await launch.evaluate(button => {
        const glyph = button.querySelector('[aria-hidden]');
        let current = button;
        while (current && getComputedStyle(current).backgroundColor === 'rgba(0, 0, 0, 0)') current = current.parentElement;
        return { text: glyph.textContent, foreground: getComputedStyle(glyph).color, background: getComputedStyle(current).backgroundColor };
      });
      assert.equal(collapsedGlyph.text, '+');
      collapsedGlyph.contrast = contrast(collapsedGlyph.foreground, collapsedGlyph.background);
      assert.ok(collapsedGlyph.contrast >= 4.5, `${id}: collapsed glyph contrast`);
    }
    await launch.click();
    let selectionEvidence;
    const assertAbsent = async () => {
      assert.equal(await page.getByRole('button', { name: /Show Turn|Tour highlights|Pause tour/ }).count(), 0);
      assert.equal(await page.getByText(/checked against/).count(), 0);
    };
    const ready = async () => {
      await page.getByRole('button', { name: 'Show Turn 1: QA first' }).waitFor();
      const image = page.getByRole('img');
      assert.ok((await image.getAttribute('src')).startsWith('blob:'));
      assert.deepEqual(await image.evaluate(image => [image.naturalWidth, image.naturalHeight]), [12, 9]);
      assert.equal(await page.getByRole('button', { name: /Show Turn/ }).count(), 3);
    };
    if (['decode-delay', 'cancel-decode'].includes(mode)) {
      await page.waitForFunction(() => window.imageUrls.created.length === 1);
      await assertAbsent(); assert.equal(await page.getByRole('img').count(), 0);
      if (mode === 'cancel-decode') {
        await launch.click();
        assert.equal(await page.evaluate(() => window.imageUrls.revoked.length), 1);
        await page.evaluate(() => window.finishDecode()); await launch.click();
      } else await page.evaluate(() => window.finishDecode());
      await ready();
    } else if (['hash-mismatch', 'dimensions', 'corrupt', 'missing', 'retry', 'reopen'].includes(mode)) {
      await page.getByText('Circuit explorer unavailable.', { exact: true }).waitFor(); await assertAbsent();
      assert.equal(await page.getByRole('img').count(), 0);
      if (mode === 'retry') { await page.getByRole('button', { name: 'Try again' }).click(); await ready(); }
      if (mode === 'reopen') { await launch.click(); await launch.click(); await ready(); }
    } else {
      await ready(); assert.equal(requests[id].images, 1);
      if (mode === 'valid') {
        // Traverse actual keyboard stops, then transfer map selection with an arrow.
        await launch.focus(); await page.keyboard.press('Tab'); await page.keyboard.press('Tab');
        const first = page.getByRole('button', { name: 'Show Turn 1: QA first' });
        assert.ok(await first.evaluate(element => element === document.activeElement && element.matches(':focus-visible')));
        const initial = assertSelectedContrast(await selectedStyles(page), `${id}: Turn 1 focus`);
        await page.keyboard.press('ArrowRight');
        const middle = page.getByRole('button', { name: 'Show Turn 3: QA middle' });
        assert.ok(await middle.evaluate(element => element === document.activeElement && element.getAttribute('aria-pressed') === 'true'));
        assert.equal(await first.getAttribute('aria-pressed'), 'false');
        assert.equal(await page.getByRole('button', { name: 'T03 QA middle' }).getAttribute('aria-pressed'), 'true');
        const byPalette = [];
        for (const palette of palettes) {
          const style = await page.addStyleTag({ content: palette.css });
          byPalette.push({ site: palette.name, ...assertSelectedContrast(await selectedStyles(page), `${id}: ${palette.name}`) });
          await style.evaluate(element => element.remove());
        }
        await page.screenshot({ path: resolve(output, `${id}-marker-focus.png`), fullPage: true });
        await page.keyboard.press('Tab'); await page.keyboard.press('Tab'); await page.keyboard.press('Tab');
        const list = page.getByRole('button', { name: 'T03 QA middle' });
        assert.ok(await list.evaluate(element => element === document.activeElement && element.matches(':focus-visible')));
        const listFocus = assertSelectedContrast(await selectedStyles(page), `${id}: selected list focus`);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${id}: horizontal overflow`);
        selectionEvidence = { collapsedGlyph, initial, byPalette, listFocus };
      }
      if (mode === 'render-error') {
        await page.getByRole('img').evaluate(image => { image.src = 'blob:invalid-for-controlled-test'; });
        await page.getByText('Circuit explorer unavailable.', { exact: true }).waitFor(); await assertAbsent();
        assert.equal(await page.evaluate(() => window.imageUrls.revoked.length), 1);
        await page.getByRole('button', { name: 'Try again' }).click(); await ready();
      }
    }
    await page.screenshot({ path: resolve(output, `${id}.png`), fullPage: true });
    await page.evaluate(() => window.unmountExplorer());
    const urls = await page.evaluate(() => window.imageUrls);
    assert.deepEqual([...urls.revoked].sort(), [...urls.created].sort(), `${id}: leaked or double-revoked URL`);
    assert.equal(errors.filter(error => error.kind === 'pageerror').length, 0);
    const expectedError = ['missing', 'retry', 'reopen'].includes(mode) ? /404/ : mode === 'render-error' ? /blob:invalid-for-controlled-test/ : null;
    assert.equal(errors.length, expectedError ? 1 : 0, `${id}: unexpected browser errors`);
    if (expectedError) assert.match(errors[0].message, expectedError);
    results.push({ mode, viewport: size, fixtureOnly: true, styles: 'F1 static export', selectionEvidence, requests: requests[id], createdUrls: urls.created.length, revokedUrls: urls.revoked.length, assertions: 'passed', errors });
    await context.close();
  }
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
await writeFile(resolve(output, 'browser-qa.json'), JSON.stringify(results, null, 2) + '\n');
console.log(JSON.stringify(results.map(({ errors, selectionEvidence, ...result }) => ({ ...result, selectionPalettesChecked: selectionEvidence?.byPalette.length ?? 0, consoleErrors: errors.length })), null, 2));
