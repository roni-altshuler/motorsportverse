// Production-export browser journeys. External requests are blocked; explicit
// negative controls change only metadata in memory, never committed data.
import { chromium } from "../../projects/f1-predictions/website/node_modules/playwright/index.mjs";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { resolve, extname } from "node:path";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";

const exported = resolve(process.argv[2]);
const output = resolve(process.argv[3]);
const baseline = process.argv[4] ? resolve(process.argv[4]) : null;
const base = "/motorsportverse/projects/f1";
const mime = {
  ".html": "text/html",
  ".txt": "text/plain",
  ".js": "application/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".webp": "image/webp",
  ".woff2": "font/woff2",
};
await mkdir(output, { recursive: true });
let serving = exported;
const server = createServer(async (req, res) => {
  try {
    const path = decodeURIComponent(
      new URL(req.url, "http://localhost").pathname,
    );
    if (path === "/favicon.ico") return res.writeHead(204).end();
    if (!path.startsWith(base + "/") && path !== base)
      throw Error("wrong base");
    const suffix = path.slice(base.length) || "/";
    let file = resolve(
      serving,
      `.${suffix.endsWith("/") ? suffix + "index.html" : suffix}`,
    );
    if (!file.startsWith(serving + "/")) throw Error("invalid path");
    let bytes;
    try {
      bytes = await readFile(file);
    } catch {
      if (extname(file)) throw Error("missing asset");
      try {
        file += ".html";
        bytes = await readFile(file);
      } catch {
        file = resolve(serving, `.${suffix}/index.html`);
        bytes = await readFile(file);
      }
    }
    res
      .writeHead(200, {
        "Content-Type": mime[extname(file)] || "application/octet-stream",
      })
      .end(bytes);
  } catch {
    res.writeHead(404).end("Not found");
  }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));
const origin = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({
  executablePath: "/usr/bin/chromium",
  headless: true,
  args: ["--no-sandbox"],
});
const results = [];
const ranking = JSON.parse(
  await readFile(resolve(exported, "data/rounds/round_16.json"), "utf8"),
);
const probability = JSON.parse(
  await readFile(resolve(exported, "data/probabilities/round_16.json"), "utf8"),
);
const cases = [
  "actual-journey",
  "missing-metadata",
  "missing-file",
  "invalid-time",
  "older-probability",
  "identity-conflict",
  "source-conflict",
  "loading",
];
const sourcePaths = [
  "projects/f1-predictions/website/src/components/RaceDetailPage.tsx",
  "projects/f1-predictions/website/src/components/race-detail/PredictionFreshnessPanel.tsx",
  "projects/f1-predictions/website/src/components/race-detail/KeyFactorsPanel.tsx",
  "projects/f1-predictions/website/src/lib/predictionFreshness.ts",
  "projects/f1-predictions/website/public/data/rounds/round_15.json",
  "projects/f1-predictions/website/public/data/rounds/round_16.json",
  "projects/f1-predictions/website/public/data/probabilities/round_16.json",
];
const sha = async (path) =>
  createHash("sha256")
    .update(await readFile(path))
    .digest("hex");
const hashes = Object.fromEntries(
  await Promise.all(sourcePaths.map(async (p) => [p, await sha(p)])),
);
async function persist() {
  await writeFile(
    resolve(output, "browser-qa.json"),
    JSON.stringify(
      { browser: browser.version(), base, hashes, cases: results },
      null,
      2,
    ) + "\n",
  );
}
try {
  for (const mobile of [false, true])
    for (const motion of ["no-preference", "reduce"]) {
      const variant = `${mobile ? "mobile" : "desktop"}-${motion}`;
      const context = await browser.newContext({
        viewport: mobile
          ? { width: 375, height: 812 }
          : { width: 1440, height: 1000 },
        reducedMotion: motion,
      });
      const page = await context.newPage();
      let entry;
      page.on("console", (message) => {
        if (message.type() === "error")
          entry?.consoleErrors.push({
            message: message.text(),
            location: message.location(),
          });
      });
      page.on("pageerror", (error) => {
        entry?.pageErrors.push({
          route: new URL(page.url()).pathname,
          message: error.message,
          stack: error.stack,
          at: new Date().toISOString(),
        });
      });
      page.on("response", (res) => {
        if (res.status() >= 400 && res.url().startsWith(origin))
          entry?.httpFailures.push({
            path: res.url().replace(origin, ""),
            status: res.status(),
          });
      });
      page.on("request", (req) => {
        if (!["GET", "HEAD"].includes(req.method()))
          entry?.nonGet.push({
            method: req.method(),
            path: req.url().replace(origin, ""),
          });
      });
      if (baseline) {
        serving = baseline;
        await page.route("**/*", (route) =>
          route.request().url().startsWith(origin)
            ? route.continue()
            : route.abort("blockedbyclient"),
        );
        await page.goto(origin + base + "/race/16", {
          waitUntil: "networkidle",
        });
        await page
          .getByRole("heading", { name: "Awaiting Qualifying", exact: true })
          .waitFor();
        assert.equal(
          await page
            .getByRole("region", { name: "Freshness & Sources" })
            .count(),
          0,
        );
        if (motion === "no-preference")
          await page
            .getByRole("heading", { name: "Awaiting Qualifying", exact: true })
            .locator("..")
            .screenshot({
              path: resolve(
                output,
                `${mobile ? "mobile" : "desktop"}-before.png`,
              ),
            });
        serving = exported;
      }
      for (const scenario of cases) {
        entry = {
          variant,
          scenario,
          controlledMetadataFixture: scenario !== "actual-journey",
          viewport: page.viewportSize(),
          motion,
          startedAt: new Date().toISOString(),
          pageErrors: [],
          consoleErrors: [],
          httpFailures: [],
          nonGet: [],
          externalBlocked: 0,
          passed: false,
        };
        results.push(entry);
        await page.unrouteAll({ behavior: "wait" });
        let release;
        const pending = new Promise((done) => {
          release = done;
        });
        await page.route("**/*", async (route) => {
          const url = route.request().url();
          if (!url.startsWith(origin)) {
            entry.externalBlocked++;
            return route.abort("blockedbyclient");
          }
          const isRank = url.endsWith("/data/rounds/round_16.json");
          const isProbability = url.endsWith(
            "/data/probabilities/round_16.json",
          );
          if (scenario === "loading" && isProbability) await pending;
          if (scenario === "missing-file" && isProbability)
            return route.fulfill({
              status: 404,
              body: "Controlled unavailable-file fixture",
            });
          if (
            (isRank || isProbability) &&
            scenario !== "actual-journey" &&
            scenario !== "missing-file" &&
            scenario !== "loading"
          ) {
            const data = structuredClone(isRank ? ranking : probability);
            if (scenario === "missing-metadata") {
              delete data.generatedAt;
              if (isRank) {
                delete data.dataFreshness;
                delete data.weatherData;
                delete data.qualifyingDataAvailable;
              }
            }
            if (scenario === "invalid-time" && isRank)
              data.generatedAt = "2026-02-30T09:00:00Z";
            if (scenario === "older-probability" && isProbability)
              data.generatedAt = "2026-01-01T00:00:00Z";
            if (scenario === "identity-conflict" && isProbability)
              data.round = 15;
            if (scenario === "source-conflict" && isRank) {
              data.qualifyingDataAvailable = true;
              data.dataFreshness.weatherSource = "api";
            }
            return route.fulfill({
              status: 200,
              contentType: "application/json",
              body: JSON.stringify(data),
            });
          }
          return route.continue();
        });
        try {
          if (scenario === "actual-journey") {
            await page.goto(origin + base + "/calendar", {
              waitUntil: "networkidle",
            });
            await page
              .locator("main")
              .locator(`a[href="${base}/race/16"]`)
              .first()
              .click();
          } else
            await page.goto(origin + base + "/race/16", {
              waitUntil: "domcontentloaded",
            });
          const panel = page.getByRole("region", {
            name: "Freshness & Sources",
          });
          await panel.waitFor();
          if (scenario === "loading") {
            await panel
              .getByText("Reading metadata…", { exact: true })
              .waitFor();
            entry.loadingObserved = true;
            release();
          }
          await panel
            .getByRole("status")
            .filter({ hasNotText: "Reading probability metadata" })
            .waitFor();
          const contents = await panel.innerText();
          assert.match(contents, /Forecast input cutoff\s+Not published/i);
          assert.match(contents, /Export times do not establish/);
          const expected = {
            "actual-journey": [
              "Different export times",
              "ranking export is older",
              "Estimated qualifying",
              "Static weather estimate",
            ],
            "missing-metadata": [
              "Incomplete time metadata",
              "Qualifying input unverified",
              "Weather input unverified",
            ],
            "missing-file": [
              "Probability export unavailable",
              "could not be loaded",
            ],
            "invalid-time": ["Timestamp needs review", "Invalid timestamp"],
            "older-probability": ["probability export is older"],
            "identity-conflict": [
              "Probability identity conflict",
              "different round or season",
            ],
            "source-conflict": [
              "Conflicting qualifying metadata",
              "Conflicting weather metadata",
            ],
            loading: ["Different export times"],
          }[scenario];
          for (const phrase of expected)
            assert.ok(contents.includes(phrase), phrase);
          const times = await panel
            .locator("time")
            .evaluateAll((nodes) => nodes.map((n) => n.dateTime));
          if (scenario === "actual-journey")
            assert.deepEqual(times, [
              "2026-06-27T17:06:41.000Z",
              "2026-09-27T01:06:55.000Z",
            ]);
          if (scenario === "identity-conflict") assert.equal(times.length, 1);
          await panel.scrollIntoViewIfNeeded();
          // Leave room for the existing sticky mobile race band in captures.
          await panel.evaluate((el) =>
            window.scrollBy({
              top: el.getBoundingClientRect().top - 88,
              behavior: "instant",
            }),
          );
          await page.waitForTimeout(100);
          entry.headingUnobscured = await panel.locator("h3").evaluate((el) => {
            const box = el.getBoundingClientRect();
            return el.contains(
              document.elementFromPoint(
                box.left + box.width / 2,
                box.top + box.height / 2,
              ),
            );
          });
          assert.equal(entry.headingUnobscured, true);
          const overflow = await panel.evaluate((el) => ({
            panel: el.scrollWidth > el.clientWidth + 1,
            page: document.documentElement.scrollWidth > innerWidth + 1,
          }));
          assert.equal(overflow.panel, false);
          entry.pageOverflow = overflow.page;
          entry.contents = contents;
          entry.times = times;
          entry.accessibilitySnapshot = await panel.ariaSnapshot();
          if (
            motion === "no-preference" &&
            [
              "actual-journey",
              "invalid-time",
              "source-conflict",
              "missing-metadata",
            ].includes(scenario)
          )
            await panel.screenshot({
              path: resolve(
                output,
                `${mobile ? "mobile" : "desktop"}-${scenario}.png`,
              ),
            });
          if (scenario === "actual-journey") {
            assert.equal(
              await page
                .getByRole("heading", { name: "Factor breakdown" })
                .count(),
              0,
            ); // preview gate retained
            await page.goto(origin + base + "/race/15", {
              waitUntil: "networkidle",
            });
            await page
              .getByRole("region", { name: "Freshness & Sources" })
              .getByText("Verified grid recorded", { exact: true })
              .waitFor();
            await page
              .getByRole("heading", { name: "Factor breakdown", exact: true })
              .waitFor();
            const picker = page.getByLabel("Driver A", { exact: true });
            const values = await picker
              .locator("option")
              .evaluateAll((nodes) => nodes.map((n) => n.value));
            await picker.selectOption(values[3]);
            assert.equal(await picker.inputValue(), values[3]);
            await picker.focus();
            await page.keyboard.press("Tab");
            entry.keyboardFocusRetained = await page.evaluate(
              () => document.activeElement !== document.body,
            );
            assert.equal(entry.keyboardFocusRetained, true);
            await page.getByRole("button", { name: /^Deep Dive$/i }).click();
            await page
              .locator("summary")
              .filter({ hasText: /^Strategy$/ })
              .click();
            await page
              .getByRole("heading", {
                name: "Strategy Comparison",
                exact: true,
              })
              .waitFor();
            entry.existingFactorAndStrategyJourney = true;
            await page.goBack({ waitUntil: "networkidle" });
            await page
              .getByRole("region", { name: "Freshness & Sources" })
              .getByText("Estimated qualifying", { exact: true })
              .waitFor();
            entry.roundReturnConfirmed = true;
          }
          assert.deepEqual(entry.pageErrors, []);
          entry.applicationErrors = entry.consoleErrors.filter((e) =>
            /route error|ReferenceError|TypeError|Minified React error/.test(
              e.message,
            ),
          );
          assert.deepEqual(entry.applicationErrors, []);
          assert.deepEqual(entry.nonGet, []);
          const unexpected = entry.httpFailures.filter(
            (x) =>
              !(
                scenario === "missing-file" &&
                x.path.endsWith("/probabilities/round_16.json")
              ),
          );
          assert.deepEqual(unexpected, []);
          entry.passed = true;
        } catch (error) {
          entry.failure = error.stack;
          entry.failureRoute = page.url().replace(origin, "");
          entry.failureBody = (await page.locator("body").innerText()).slice(
            0,
            12000,
          );
          await page.screenshot({
            path: resolve(output, `${variant}-${scenario}-failure.png`),
            fullPage: true,
          });
          await persist();
          throw error;
        } finally {
          release();
          await persist();
        }
      }
      await context.close();
    }
  console.log(
    JSON.stringify({
      passed: results.filter((r) => r.passed).length,
      total: results.length,
      output,
    }),
  );
} finally {
  await persist();
  await browser.close();
  await new Promise((done) => server.close(done));
}
