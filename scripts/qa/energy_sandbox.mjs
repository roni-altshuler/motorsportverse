// Production-export journeys for an original synthetic exercise. No provider
// traffic or data fixtures are needed; all controls use the actual client math.
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
const hash = async (path) =>
  createHash("sha256")
    .update(await readFile(path))
    .digest("hex");
const sourcePaths = [
  "scripts/qa/energy_sandbox.mjs",
  "projects/f1-predictions/website/src/app/circuits/page.tsx",
  "projects/f1-predictions/website/src/components/engineering/EnergySandbox.tsx",
  "projects/f1-predictions/website/src/lib/energySandbox.ts",
  "projects/f1-predictions/website/src/__tests__/energySandbox.test.tsx",
  "projects/f1-predictions/website/src/components/ui/CircuitReplayWorkspace.tsx",
  "projects/f1-predictions/website/public/data/season_tracker.json",
  "projects/f1-predictions/website/public/data/rounds/round_16.json",
  "projects/f1-predictions/website/public/data/probabilities/round_16.json",
];
const hashes = Object.fromEntries(
  await Promise.all(sourcePaths.map(async (p) => [p, await hash(p)])),
);
const report = {
  browser: browser.version(),
  base,
  sourceHashes: hashes,
  exportedCircuitHtmlHash: await hash(resolve(exported, "circuits.html")),
  baselineCircuitHtmlHash: baseline
    ? await hash(resolve(baseline, "circuits.html"))
    : null,
  exportBuildId: (
    await readFile(resolve(exported, "../.next/BUILD_ID"), "utf8")
  ).trim(),
  variants: [],
};
async function persist() {
  await writeFile(
    resolve(output, "browser-qa.json"),
    JSON.stringify(report, null, 2) + "\n",
  );
}

try {
  for (const mobile of [false, true])
    for (const motion of ["no-preference", "reduce"]) {
      const variant = `${mobile ? "mobile" : "desktop"}-${motion}`;
      const entry = {
        variant,
        viewport: mobile
          ? { width: 375, height: 812 }
          : { width: 1440, height: 1000 },
        motion,
        startedAt: new Date().toISOString(),
        checks: [],
        consoleErrors: [],
        expectedBlockedResourceErrors: [],
        unexpectedConsoleErrors: [],
        pageErrors: [],
        httpFailures: [],
        nonGet: [],
        requestsDuringCalculation: [],
        navigationAndStaticPrefetches: [],
        unexpectedCalculationRequests: [],
        externalBlocked: 0,
        passed: false,
      };
      report.variants.push(entry);
      const context = await browser.newContext({
        viewport: entry.viewport,
        reducedMotion: motion,
      });
      const page = await context.newPage();
      const blockedUrls = new Set();
      let calculating = false;
      async function capture(_locator, filename) {
        // Full-document screenshots resize the capture viewport internally.
        // Use a separate real tab so they cannot disturb Lenis or the scroll
        // state of the fixed-viewport user journey.
        const values = await page
          .locator("#energy-sandbox input")
          .evaluateAll((inputs) => inputs.map((input) => input.value));
        const open = await page
          .locator("#energy-sandbox details")
          .evaluateAll((details) => details.some((detail) => detail.open));
        const camera = await context.newPage();
        camera.on("console", (msg) => {
          if (msg.type() === "error")
            entry.consoleErrors.push({
              message: msg.text(),
              location: msg.location(),
              screenshotTab: filename,
            });
        });
        camera.on("pageerror", (error) =>
          entry.pageErrors.push({
            message: error.message,
            screenshotTab: filename,
          }),
        );
        await camera.route("**/*", (route) => {
          if (route.request().url().startsWith(origin)) return route.continue();
          blockedUrls.add(route.request().url());
          entry.externalBlocked++;
          return route.abort("blockedbyclient");
        });
        await camera.goto(origin + base + "/circuits", {
          waitUntil: "networkidle",
        });
        for (let i = 0; i < values.length; i++)
          await camera.locator("#energy-sandbox input").nth(i).fill(values[i]);
        if (open) await camera.locator("#energy-sandbox summary").click();
        await camera.evaluate(() =>
          window.scrollTo({ top: 0, behavior: "instant" }),
        );
        await camera.waitForTimeout(300); // Existing navbar settles in 180 ms.
        const selector = filename.endsWith("before.png")
          ? '[aria-label="Circuit workspace"]'
          : filename.endsWith("controls.png")
            ? "#energy-sandbox form"
            : filename.endsWith("ledger.png")
              ? "#energy-sandbox details"
              : filename === "desktop-overview.png"
                ? "#energy-sandbox"
                : '#energy-sandbox [data-testid="energy-results"]';
        const clip = await camera.locator(selector).boundingBox();
        await camera.screenshot({
          path: resolve(output, filename),
          fullPage: true,
          clip,
        });
        await camera.close();
      }
      page.on("console", (msg) => {
        if (msg.type() === "error")
          entry.consoleErrors.push({
            message: msg.text(),
            location: msg.location(),
          });
      });
      page.on("pageerror", (error) =>
        entry.pageErrors.push({
          message: error.message,
          stack: error.stack,
          route: new URL(page.url()).pathname,
        }),
      );
      page.on("response", (res) => {
        if (res.status() >= 400 && res.url().startsWith(origin))
          entry.httpFailures.push({
            path: res.url().replace(origin, ""),
            status: res.status(),
          });
      });
      page.on("request", (req) => {
        if (calculating && req.url().startsWith(origin))
          entry.requestsDuringCalculation.push({
            method: req.method(),
            url: req.url().replace(origin, ""),
          });
        if (!["GET", "HEAD"].includes(req.method()))
          entry.nonGet.push({ method: req.method(), url: req.url() });
      });
      await page.route("**/*", (route) => {
        if (route.request().url().startsWith(origin)) return route.continue();
        entry.externalBlocked++;
        blockedUrls.add(route.request().url());
        return route.abort("blockedbyclient");
      });
      if (baseline && motion === "no-preference") {
        serving = baseline;
        await page.goto(origin + base + "/circuits", {
          waitUntil: "networkidle",
        });
        await page
          .getByRole("button", { name: "Try fictional demo" })
          .waitFor();
        assert.equal(await page.locator("#energy-sandbox").count(), 0);
        await capture(
          page.getByRole("region", { name: "Circuit workspace", exact: true }),
          `${mobile ? "mobile" : "desktop"}-before.png`,
        );
        entry.checks.push(
          "Baseline export: local-capture workspace present, no energy sandbox",
        );
        serving = exported;
      }
      await page.goto(origin + base + "/race/16", { waitUntil: "networkidle" });
      await page
        .locator("main")
        .getByRole("link", { name: /Circuit workspace/ })
        .click();
      const sandbox = page.getByRole("region", {
        name: "Energy management sandbox.",
      });
      await sandbox.waitFor();
      await page
        .getByRole("navigation", { name: "Workspace sections" })
        .getByRole("link", { name: "Energy sandbox" })
        .click();
      assert.ok(page.url().endsWith("/circuits#energy-sandbox"));
      await page.waitForFunction(() => {
        const el = document.getElementById("energy-sandbox");
        return (
          el &&
          el.getBoundingClientRect().top < 180 &&
          el.getBoundingClientRect().top > -20
        );
      });
      entry.checks.push(
        "Actual race → circuit client navigation, anchor and hydration",
      );
      const input = (name) => sandbox.getByRole("spinbutton", { name });
      const status = sandbox.getByRole("status");
      const reset = sandbox.getByRole("button", { name: /^Reset$/ });
      const metric = (name) => sandbox.locator(`[data-metric="${name}"]`);
      await status.getByText(/Final charge 24.2 percent/).waitFor();
      assert.equal(
        (await metric("Deployment delivered").innerText()).trim(),
        "3.000 kWh",
      );
      assert.equal(
        (await metric("Energy recovered").innerText()).trim(),
        "1.500 kWh",
      );
      assert.match(await sandbox.innerText(), /Synthetic \/ Educational/i);
      assert.match(await sandbox.innerText(), /no measured telemetry/);
      await page.waitForLoadState("networkidle");
      calculating = true;
      if (motion === "no-preference" && !mobile)
        await capture(sandbox, "desktop-overview.png");
      if (motion === "no-preference" && mobile) {
        await capture(
          sandbox.getByRole("form", { name: "Your assumptions" }),
          "mobile-controls.png",
        );
        await capture(
          sandbox.getByTestId("energy-results"),
          "mobile-chart.png",
        );
      }
      entry.checks.push(
        "Default analytical output, visible units and synthetic limitations",
      );
      assert.equal(
        await sandbox
          .getByRole("img", { name: "Synthetic charge over 360 seconds" })
          .locator("svg:visible")
          .count(),
        1,
      );
      const chart = await sandbox.getByRole("img").boundingBox();
      assert.ok(chart.width <= entry.viewport.width && chart.height > 150);
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
      );
      entry.checks.push(
        "Responsive chart, one visible trace, no document overflow",
      );

      await input("Starting charge (%)").focus();
      await page.keyboard.press("ArrowUp");
      assert.equal(await input("Starting charge (%)").inputValue(), "71");
      await status.getByText(/Final charge 25.2 percent/).waitFor();
      await reset.focus();
      await page.keyboard.press("Enter");
      await status.getByText(/Final charge 24.2 percent/).waitFor();
      await input("Deployment output (kW)").focus();
      const url = page.url();
      await page.keyboard.press("Enter");
      assert.equal(page.url(), url);
      entry.checks.push(
        "Keyboard number adjustment, reset and non-navigating Enter",
      );

      await input("Deployment output (kW)").fill("0");
      await input("Available regeneration (kW)").fill("0");
      await status.getByText(/Final charge 70.0 percent/).waitFor();
      assert.equal(
        (await metric("Deployment delivered").innerText()).trim(),
        "0.000 kWh",
      );
      assert.equal(
        (await metric("Energy recovered").innerText()).trim(),
        "0.000 kWh",
      );
      entry.checks.push("Zero flow preserves initial charge");

      await input("Starting charge (%)").fill("0");
      await input("Deployment output (kW)").fill("200");
      await status.getByText(/Final charge 0.0 percent/).waitFor();
      assert.match(
        await sandbox.innerText(),
        /10.000 kWh of requested deployment could not be supplied/,
      );
      assert.equal(
        (await metric("Deployment delivered").innerText()).trim(),
        "0.000 kWh",
      );
      if (motion === "no-preference" && !mobile)
        await capture(
          sandbox.getByTestId("energy-results"),
          "desktop-empty-limit.png",
        );
      entry.checks.push(
        "Empty capacity curtails demand without negative charge",
      );

      await input("Starting charge (%)").fill("100");
      await input("Deployment output (kW)").fill("0");
      await input("Available regeneration (kW)").fill("150");
      await status.getByText(/Final charge 100.0 percent/).waitFor();
      assert.match(
        await sandbox.innerText(),
        /5.000 kWh of incoming regeneration was rejected/,
      );
      assert.equal(
        (await metric("Energy recovered").innerText()).trim(),
        "0.000 kWh",
      );
      if (motion === "no-preference" && mobile)
        await capture(
          sandbox.getByTestId("energy-results"),
          "mobile-full-limit.png",
        );
      entry.checks.push(
        "Full capacity rejects regeneration without exceeding 100%",
      );

      await input("Usable capacity (kWh)").fill("0.73389");
      await status.getByText(/Final charge 100.0 percent/).waitFor();
      assert.equal(
        (await metric("Energy recovered").innerText()).trim(),
        "0.000 kWh",
      );
      await sandbox.locator("summary").click();
      assert.match(
        await sandbox
          .getByText("Conversion losses", { exact: true })
          .locator("..")
          .innerText(),
        /0.000 kWh/,
      );
      await sandbox.locator("summary").click();
      entry.checks.push(
        "Fractional full capacity retains exactly full charge with zero recovery/loss",
      );

      await input("Usable capacity (kWh)").fill("");
      assert.equal(
        await input("Usable capacity (kWh)").getAttribute("aria-invalid"),
        "true",
      );
      assert.match(await status.innerText(), /Results paused/);
      assert.equal(await sandbox.getByTestId("energy-results").count(), 0);
      const described = await input("Usable capacity (kWh)").getAttribute(
        "aria-describedby",
      );
      assert.ok(described.includes("-error"));
      await input("Usable capacity (kWh)").fill("21");
      assert.match(
        await sandbox.innerText(),
        /Enter a number from 0.5 to 20 kWh/,
      );
      await input("Usable capacity (kWh)").fill("4.123");
      await input("Conversion efficiency (%)").fill("49");
      assert.equal(await sandbox.getByTestId("energy-results").count(), 0);
      await input("Conversion efficiency (%)").fill("91.25");
      await sandbox.getByTestId("energy-results").waitFor();
      await reset.click();
      await status.getByText(/Final charge 24.2 percent/).waitFor();
      entry.checks.push(
        "Blank, out-of-range and decimal handling; no stale results; reset",
      );

      const summary = sandbox.locator("summary");
      await summary.focus();
      await page.keyboard.press("Enter");
      await sandbox.getByRole("table").waitFor({ state: "visible" });
      assert.equal(
        await sandbox.getByRole("table").locator("tbody tr").count(),
        6,
      );
      const ledgerRegion = sandbox.getByRole("region", {
        name: "Cycle values, horizontally scrollable",
      });
      if (mobile) {
        await ledgerRegion.focus();
        await page.keyboard.press("ArrowRight");
        await page.waitForFunction(
          () =>
            document.querySelector(
              '[aria-label="Cycle values, horizontally scrollable"]',
            ).scrollLeft > 0,
        );
        assert.ok(await ledgerRegion.evaluate((el) => el.scrollLeft > 0));
      }
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
      );
      if (motion === "no-preference")
        await capture(
          sandbox.locator("details"),
          `${mobile ? "mobile" : "desktop"}-ledger.png`,
        );
      entry.checks.push(
        "Keyboard details, six cycle rows and contained mobile table scrolling",
      );
      for (const [name, suffix] of [
        ["MATLAB Onramp", "matlab-onramp/gettingstarted"],
        ["Simulink Onramp", "simulink-onramp/simulink"],
        ["Simscape Battery Onramp", "simscape-battery-onramp/orsb"],
      ]) {
        const link = sandbox.getByRole("link", { name: new RegExp(name) });
        assert.equal(
          await link.getAttribute("href"),
          `https://matlabacademy.mathworks.com/details/${suffix}`,
        );
        assert.equal(await link.getAttribute("rel"), "noopener noreferrer");
        assert.equal(await link.getAttribute("target"), "_blank");
      }
      assert.match(await sandbox.innerText(), /require a MathWorks account/);
      entry.checks.push(
        "Exact official learning links, external-tab labels and account disclosure",
      );

      calculating = false;
      // Scrolling can expose existing Next navigation links and start their
      // static prefetches. Keep those requests in the raw log; reject any data,
      // API or other request rather than attributing all page traffic to math.
      for (const request of entry.requestsDuringCalculation) {
        const path = new URL(request.url, origin).pathname;
        const navigation = ["about", "calendar", "standings"].some(
          (route) =>
            (request.method === "HEAD" && path === `${base}/${route}`) ||
            (request.method === "GET" &&
              path.startsWith(`${base}/${route}/__next.`) &&
              path.endsWith(".txt")),
        );
        const asset =
          request.method === "GET" &&
          path.startsWith(`${base}/_next/static/`) &&
          /\.(?:js|css)$/.test(path);
        (navigation || asset
          ? entry.navigationAndStaticPrefetches
          : entry.unexpectedCalculationRequests
        ).push(request);
      }
      assert.deepEqual(entry.unexpectedCalculationRequests, []);
      entry.checks.push(
        "Local assumption calculations: no data/API requests; existing navigation/static prefetches recorded separately",
      );
      await page
        .getByRole("navigation", { name: "Workspace sections" })
        .getByRole("link", { name: "Local captures" })
        .click();
      await page.waitForFunction(() => {
        const top = document
          .getElementById("local-capture")
          .getBoundingClientRect().top;
        // Expansion can add up to 32 px after the native anchor lands. Both
        // positions keep the section visible below the header, below the
        // collapse threshold, with no feedback loop.
        return top >= 150 && top <= 210 && scrollY < 80;
      });
      entry.localCaptureAnchor = await page.evaluate(() => ({
        top: document.getElementById("local-capture").getBoundingClientRect()
          .top,
        scrollY,
      }));
      await page.getByRole("button", { name: "Try fictional demo" }).click();
      await page.getByRole("button", { name: "Clear capture" }).waitFor();
      await page.getByRole("button", { name: "Clear capture" }).click();
      assert.equal(
        await page.getByRole("button", { name: "Clear capture" }).count(),
        0,
      );
      await page.reload({ waitUntil: "networkidle" });
      await status.getByText(/Final charge 24.2 percent/).waitFor();
      entry.checks.push(
        "Existing fictional capture remains usable; reload has deterministic defaults",
      );
      if (motion === "reduce") {
        const animated = await sandbox.evaluate(
          (el) =>
            el
              .getAnimations({ subtree: true })
              .filter((animation) => animation.playState === "running").length,
        );
        assert.equal(animated, 0);
        entry.checks.push(
          "Reduced-motion preference: no running sandbox animations",
        );
      }
      // Keep the raw log. A deliberately blocked external image's browser error
      // is expected only when the exact URL was intercepted and the message is
      // exactly the network abort. Caught React errors still fail the journey.
      for (const error of entry.consoleErrors) {
        const expected =
          blockedUrls.has(error.location.url) &&
          /^Failed to load resource: net::ERR_BLOCKED_BY_CLIENT(?:\.Inspector)?$/.test(
            error.message,
          );
        (expected
          ? entry.expectedBlockedResourceErrors
          : entry.unexpectedConsoleErrors
        ).push(error);
      }
      assert.deepEqual(entry.unexpectedConsoleErrors, []);
      assert.deepEqual(entry.pageErrors, []);
      assert.deepEqual(entry.httpFailures, []);
      assert.deepEqual(entry.nonGet, []);
      entry.passed = true;
      entry.finishedAt = new Date().toISOString();
      await persist();
      await context.close();
    }
} catch (error) {
  report.failure = { message: error.message, stack: error.stack };
  await persist();
  throw error;
} finally {
  await persist();
  await browser.close();
  await new Promise((done) => server.close(done));
}
console.log(
  `Passed ${report.variants.length} desktop/mobile production-export journeys.`,
);
