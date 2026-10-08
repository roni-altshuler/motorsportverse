import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { chromium } from "../../projects/f1-predictions/website/node_modules/playwright/index.mjs";
import { waitForRouteReady } from "./route_readiness.mjs";

let browser;
before(async () => {
  browser = await chromium.launch({
    executablePath: "/usr/bin/chromium",
    args: ["--no-sandbox"],
  });
});
after(async () => {
  await browser.close();
});
const expected = {
  path: "blank",
  headings: [{ level: 1, text: "Australian Grand Prix" }],
  text: ["Albert Park"],
};

test("matching URL and main cannot pass with the preceding route's content", async () => {
  const page = await browser.newPage();
  await page.setContent(
    "<main><h1>Season Calendar</h1><p>Albert Park</p></main>",
  );
  await assert.rejects(waitForRouteReady(page, expected, 200), /Timeout/);
  await page.setContent(
    '<main><h1><span role="img" aria-label="Australia flag">🏁</span>Australian Grand Prix</h1><p>Albert Park</p></main>',
  );
  const result = await waitForRouteReady(page, expected);
  assert.equal(result.expected.headings[0].text, "Australian Grand Prix");
  assert.ok(result.stableRenderedFrames >= 3);
  await page.close();
});

test("destination identity cannot pass while its local data fetch remains pending", async () => {
  const page = await browser.newPage();
  await page.setContent(
    "<main><h1>Australian Grand Prix</h1><p>Albert Park</p></main>",
  );
  await page.evaluate(() => {
    window.__qaPendingFetch = 1;
  });
  await assert.rejects(waitForRouteReady(page, expected, 200), /Timeout/);
  await page.evaluate(() => {
    window.__qaPendingFetch = 0;
  });
  assert.equal(
    (await waitForRouteReady(page, expected)).pendingLocalFetches,
    0,
  );
  await page.close();
});

test("destination identity cannot pass with a visible loading indicator", async () => {
  const page = await browser.newPage();
  await page.setContent(
    '<main><h1>Australian Grand Prix</h1><p>Albert Park</p><p class="loading-pulse">Loading race data</p></main>',
  );
  await assert.rejects(waitForRouteReady(page, expected, 200), /Timeout/);
  await page.locator(".loading-pulse").evaluate((el) => el.remove());
  assert.equal((await waitForRouteReady(page, expected)).loadingIndicators, 0);
  await page.close();
});

test("destination identity cannot pass before its primary heading is visible", async () => {
  const page = await browser.newPage();
  await page.setContent(
    '<main><section style="opacity:0"><h1>Australian Grand Prix</h1><p>Albert Park</p></section></main>',
  );
  await assert.rejects(waitForRouteReady(page, expected, 200), /Timeout/);
  await page.locator("section").evaluate((el) => {
    el.style.opacity = "1";
  });
  const result = await waitForRouteReady(page, expected);
  assert.equal(result.primaryHeadingOpacity, 1);
  assert.ok(result.primaryHeadingGeometry.width > 0);
  await page.close();
});

test("destination identity waits for its moving heading to settle", async () => {
  const page = await browser.newPage();
  await page.setContent(
    "<style>@keyframes moving { from { transform:translateY(0) } to { transform:translateY(1000px) } } section { animation:moving 100ms linear infinite }</style><main><section><h1>Australian Grand Prix</h1><p>Albert Park</p></section></main>",
  );
  await assert.rejects(waitForRouteReady(page, expected, 200), /Timeout/);
  await page.locator("section").evaluate((el) => {
    el.style.animation = "none";
  });
  const result = await waitForRouteReady(page, expected);
  assert.ok(result.stableRenderedFrames >= 3);
  assert.equal(result.geometryTolerancePx, 0.5);
  await page.close();
});
