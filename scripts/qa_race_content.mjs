// Browser assertions for visible race content, beyond headings in the DOM.
import assert from 'node:assert/strict';

export async function paintState(locator) {
  return locator.evaluate(element => {
    let opacity = 1;
    const hiddenAncestors = [];
    for (let node = element; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      opacity *= Number(style.opacity);
      if (style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) < .99) {
        hiddenAncestors.push({ tag: node.tagName, className: node.className, opacity: style.opacity, display: style.display, visibility: style.visibility });
      }
    }
    const rect = element.getBoundingClientRect();
    const x = Math.max(1, Math.min(innerWidth - 1, rect.left + rect.width / 2));
    const y = Math.max(1, Math.min(innerHeight - 1, rect.top + rect.height / 2));
    const covering = document.elementFromPoint(x, y);
    return {
      opacity, hiddenAncestors, width: rect.width, height: rect.height,
      intersectsViewport: rect.bottom > 0 && rect.top < innerHeight && rect.right > 0 && rect.left < innerWidth,
      covered: !!covering && !element.contains(covering) && !covering.contains(element),
      text: element.textContent?.trim(),
    };
  });
}

export async function scrollAndCheckPaint(page, locator, label, timeoutMs = 5000) {
  const top = await locator.evaluate(element => Math.max(0, scrollY + element.getBoundingClientRect().top - innerHeight * .35));
  // Real document scrolling triggers the same intersection observers as browsing.
  await page.evaluate(top => window.scrollTo({ top, behavior: 'instant' }), top);
  const deadline = Date.now() + timeoutMs;
  let state;
  do {
    state = await paintState(locator);
    if (state.opacity >= .99 && state.intersectsViewport && !state.covered && !state.hiddenAncestors.length) break;
    await page.waitForTimeout(50);
  } while (Date.now() < deadline);
  assert.ok(state.opacity >= .99 && !state.hiddenAncestors.length, `${label}: content remains hidden: ${JSON.stringify(state)}`);
  assert.ok(state.width > 0 && state.height > 0 && state.intersectsViewport && !state.covered, `${label}: content is not painted in the viewport: ${JSON.stringify(state)}`);
  return { label, top: await page.evaluate(() => scrollY), ...state };
}

export async function revealRaceContent(page, round, screenshot) {
  const block = round.feature ?? round.race;
  assert.ok(block?.classification?.length, 'Committed round needs classification data');
  const main = page.getByRole('main');
  const podiumHeading = main.getByRole('heading', { name: /^(Race Podium|Predicted Podium)$/ });
  const podium = podiumHeading.locator('../../..');
  const probability = main.getByRole('heading', { name: 'Win vs Podium', exact: true }).locator('../../..');
  const classification = main.locator('table').first();
  const expectedPodium = round.completed && block.classification.some(entry => entry.actualPosition != null)
    ? [...block.classification].filter(entry => entry.actualPosition != null).sort((a, b) => a.actualPosition - b.actualPosition).slice(0, 3)
    : block.classification.slice(0, 3);
  const checks = [];
  checks.push(await scrollAndCheckPaint(page, podiumHeading, 'podium heading'));
  for (const entry of expectedPodium) {
    const name = podium.getByText(entry.name, { exact: true });
    checks.push(await scrollAndCheckPaint(page, name, `podium ${entry.code}`));
    if (screenshot) await screenshot(`podium-${entry.code}`, name);
  }
  const probabilityLabel = probability.getByText(/^Win vs podium probability$/i);
  checks.push(await scrollAndCheckPaint(page, probabilityLabel, 'probability board'));
  // The probability board renders twelve rows and their coloured bar segments.
  const probabilityRows = probabilityLabel.locator('..').locator(':scope > div').first().locator(':scope > div');
  assert.equal(await probabilityRows.count(), Math.min(12, block.classification.length));
  for (let i = 0; i < Math.min(12, block.classification.length); i++) {
    assert.ok((await probabilityRows.nth(i).getAttribute('title')).includes(block.classification[i].name), `probability row ${i}: wrong published identity`);
    checks.push(await scrollAndCheckPaint(page, probabilityRows.nth(i), `probability row ${i}`));
  }
  if (screenshot) await screenshot('probabilities', probability);
  assert.equal(await classification.locator('tbody tr').count(), block.classification.length);
  for (let i = 0; i < block.classification.length; i++) {
    const entry = block.classification[i];
    const row = classification.locator('tbody tr').nth(i);
    assert.ok((await row.innerText()).includes(entry.name), `classification ${entry.code}: wrong published identity`);
    checks.push(await scrollAndCheckPaint(page, row, `classification ${entry.code}`));
    if (screenshot && [0, Math.floor(block.classification.length / 2), block.classification.length - 1].includes(i)) await screenshot(`classification-${i}`, row);
  }
  return { checks, podiumNames: expectedPodium.map(entry => entry.name), probabilityRows: Math.min(12, block.classification.length), classificationRows: block.classification.length };
}

export async function scrollWholePage(page) {
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  const stops = [];
  for (let top = 0; top < height; top += 500) {
    await page.evaluate(top => window.scrollTo({ top, behavior: 'instant' }), top);
    await page.waitForTimeout(150);
    stops.push(await page.evaluate(() => scrollY));
  }
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(150);
  return stops;
}
