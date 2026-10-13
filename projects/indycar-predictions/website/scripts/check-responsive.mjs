// Focused browser regression for the homepage's long forecast controls.
// node scripts/check-responsive.mjs http://127.0.0.1:3387 /tmp/indy-responsive
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { chromium } from "playwright";

const base = process.argv[2] || "http://127.0.0.1:3387";
const output = resolve(process.argv[3] || "/tmp/indy-responsive");
const report = { base, cases: [] };
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  headless: true,
});
try {
  for (const [name, viewport] of [
    ["desktop", { width: 1440, height: 900 }],
    ["mobile", { width: 390, height: 844 }],
    ["narrow", { width: 320, height: 780 }],
  ]) {
    const page = await browser.newPage({ viewport, reducedMotion: "no-preference" });
    const entry = { name, viewport, errors: [] };
    page.on("pageerror", error => entry.errors.push(error.message));
    await page.route("**/*", route =>
      new URL(route.request().url()).origin === new URL(base).origin
        ? route.continue() : route.abort(),
    );
    try {
      await page.goto(base, { waitUntil: "networkidle" });
      await page.evaluate(() => document.fonts.ready);
      const hero = page.locator(".hero-photo-band");
      const forecast = hero.getByRole("link", { name: "View snapshot forecast →" });
      const classification = page.getByRole("link", { name: "Full classification", exact: true });
      const destination = await forecast.getAttribute("href");
      const raceTitle = await hero.getByText("Forecast in this snapshot", { exact: true })
        .locator("..").getByRole("heading", { level: 2 }).textContent();
      assert(raceTitle, "featured race title is present");
      assert.equal(await classification.getAttribute("href"), destination);
      entry.mainTextSha256 = createHash("sha256")
        .update((await page.locator("main").textContent()).replace(/\s+/g, " ").trim()).digest("hex");
      entry.documentWidth = await page.evaluate(() => document.documentElement.scrollWidth);
      entry.heroWidth = (await hero.boundingBox()).width;
      entry.forecastBounds = await forecast.boundingBox();
      await page.screenshot({ path: resolve(output, `${name}-hero.png`) });
      await forecast.scrollIntoViewIfNeeded();
      await page.waitForTimeout(400);
      await page.screenshot({ path: resolve(output, `${name}-forecast-control.png`) });
      await classification.scrollIntoViewIfNeeded();
      await page.waitForTimeout(400);
      entry.classificationBounds = await classification.boundingBox();
      await page.screenshot({ path: resolve(output, `${name}-classification.png`) });
      assert(entry.documentWidth <= viewport.width + 1, "document overflows viewport");
      for (const box of [entry.forecastBounds, entry.classificationBounds]) {
        assert(box.x >= 0 && box.x + box.width <= viewport.width + 1, "forecast control is clipped");
      }
      assert(entry.forecastBounds.height >= 44, "forecast control retains a 44px minimum target");
      // Remove existing document clipping in the test so a masking fix cannot pass.
      const style = await page.addStyleTag({ content: "html,body { overflow-x: visible !important; }" });
      entry.unmaskedWidth = await page.evaluate(() => document.documentElement.scrollWidth);
      assert(entry.unmaskedWidth <= viewport.width + 1, "overflow is only concealed by document clipping");
      await style.evaluate(node => node.remove());
      if (name === "narrow") {
        const calendar = hero.getByRole("button", { name: /Add .* to your calendar/ });
        await calendar.focus();
        const download = page.waitForEvent("download");
        await page.keyboard.press("Enter");
        entry.calendarDownload = (await download).suggestedFilename();
        assert(entry.calendarDownload.endsWith(".ics"));
        await classification.focus();
        assert(await classification.evaluate(node => node === document.activeElement));
        await page.keyboard.press("Enter");
        await page.waitForURL(`${base}${destination}`);
        await page.locator("main").getByText(raceTitle, { exact: true }).waitFor();
        const track = page.locator("summary").filter({ hasText: "Track & Telemetry" });
        await track.focus();
        await page.keyboard.press("Enter");
        const panel = track.locator("..");
        assert(await panel.evaluate(node => node.open));
        entry.circuitState = await panel.getByRole("img", { name: "Circuit layout" }).count()
          ? "Circuit layout rendered" : "Circuit layout unavailable";
        if (entry.circuitState === "Circuit layout unavailable") {
          await panel.getByText("Circuit layout unavailable", { exact: true }).waitFor();
        }
        await panel.scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(output, "narrow-circuit.png") });
      }
      assert.deepEqual(entry.errors, []);
      entry.passed = true;
    } catch (error) {
      entry.passed = false;
      entry.error = error.message;
    } finally {
      await page.close();
      report.cases.push(entry);
      await writeFile(resolve(output, "responsive.json"), JSON.stringify(report, null, 2) + "\n");
    }
  }
} finally {
  await browser.close();
}
console.log(JSON.stringify(report));
if (report.cases.some(entry => !entry.passed)) process.exitCode = 1;
