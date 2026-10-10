// Real static-export interactions; all imported coordinates below are original QA samples.
import { chromium } from "../../projects/f1-predictions/website/node_modules/playwright/index.mjs";
import { createServer } from "node:http";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { resolve, extname } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";
import { waitForRouteReady } from "../lib/route_readiness.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const output = resolve(process.argv[2] || "/tmp/circuit-selection-qa");
const mode = process.argv[3] || "final";
assert.ok(["baseline", "final"].includes(mode));
const base = "/motorsportverse/projects/f1";
const exported = resolve(root, "projects/f1-predictions/website/out");
await mkdir(output, { recursive: true });
const mime = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".txt": "text/plain",
  ".json": "application/json",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webp": "image/webp",
  ".woff2": "font/woff2",
  ".ico": "image/x-icon",
};
const server = createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(
      new URL(request.url, "http://localhost").pathname,
    );
    if (pathname === "/favicon.ico") {
      response.writeHead(204);
      response.end();
      return;
    }
    assert.ok(pathname === base || pathname.startsWith(base + "/"));
    const path = pathname.slice(base.length) || "/";
    let file = resolve(exported, "." + path);
    assert.ok(file === exported || file.startsWith(exported + "/"));
    let bytes;
    for (const candidate of [
      file,
      ...(extname(file) ? [] : [file + ".html", resolve(file, "index.html")]),
    ]) {
      try {
        bytes = await readFile(candidate);
        file = candidate;
        break;
      } catch {}
    }
    if (!bytes) throw new Error("Missing export resource");
    response.writeHead(200, {
      "Content-Type": mime[extname(file)] || "application/octet-stream",
    });
    response.end(request.method === "HEAD" ? undefined : bytes);
  } catch {
    response.writeHead(404);
    response.end("Not found");
  }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));
const origin = "http://127.0.0.1:" + server.address().port;
const browser = await chromium.launch({
  executablePath: "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const results = [];
const capture = [
  {
    frame_index: 0,
    track_geometry: {
      x: [0, 120, 120, 0, 0],
      y: [0, 0, 80, 80, 0],
      rotation_deg: 37,
    },
    frame: {
      t: 0,
      drivers: {
        AAA: { name: "QA Driver A", x: 35, y: 25 },
        BBB: { name: "QA Driver B", x: 85, y: 55 },
      },
    },
  },
  {
    frame_index: 1,
    frame: {
      t: 1,
      drivers: {
        AAA: { name: "QA Driver A", x: null, y: null },
        BBB: { name: "QA Driver B", x: 10000, y: 10000 },
      },
    },
  },
  { frame_index: 2, frame: { t: 2, drivers: {} } },
  {
    frame_index: 3,
    frame: {
      t: 3,
      drivers: {
        AAA: { name: "QA Driver A", x: 35, y: 25 },
        BBB: { name: "QA Driver B", x: 35, y: 25 },
      },
    },
  },
]
  .map((frame) => JSON.stringify(frame))
  .join("\n");
try {
  for (const [size, viewport] of [
    ["desktop", { width: 1440, height: 1000 }],
    ["mobile", { width: 390, height: 844 }],
    ...(mode === "final" ? [["narrow", { width: 320, height: 740 }]] : []),
  ]) {
    for (const motion of ["no-preference", "reduce"]) {
      const label = `${size}-${motion}`;
      const touch = mode === "final" && size !== "desktop";
      const context = await browser.newContext({
        viewport,
        reducedMotion: motion,
        hasTouch: touch,
        isMobile: touch,
      });
      const page = await context.newPage();
      const errors = [],
        consoleEntries = [],
        failedResources = [],
        blockedExternal = [];
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("console", (message) => {
        if (["error", "warning"].includes(message.type()))
          consoleEntries.push({ type: message.type(), text: message.text() });
      });
      page.on("response", (response) => {
        if (response.status() >= 400)
          failedResources.push({
            url: response.url().replace(origin, ""),
            status: response.status(),
          });
      });
      await context.route("**/*", (route) => {
        if (new URL(route.request().url()).origin === origin)
          return route.continue();
        blockedExternal.push(route.request().url());
        return route.abort("blockedbyclient");
      });
      try {
        assert.equal(
          (
            await page.goto(origin + base + "/circuits", {
              waitUntil: "networkidle",
            })
          ).status(),
          200,
        );
        await waitForRouteReady(page, {
          path: base + "/circuits",
          headings: [{ level: 1, text: "Explore the circuit." }],
        });
        const workspace = page.getByRole("region", {
          name: "Circuit workspace",
          exact: true,
        });
        const series = workspace.getByRole("combobox");
        const seriesOptions = await series.locator("option").allTextContents();
        for (const option of seriesOptions) {
          await series.selectOption(option);
          await workspace
            .getByText("Circuit map unavailable", { exact: true })
            .waitFor();
          assert.equal(await workspace.locator("svg").count(), 0);
        }
        await series.selectOption("Formula 1");
        await workspace
          .getByRole("button", { name: "Try fictional demo", exact: true })
          .click();
        await workspace
          .getByText("Fictional demo · Not a real circuit or race", {
            exact: true,
          })
          .waitFor();
        const map = workspace.getByRole("img", {
          name: "Fictional circuit view",
          exact: true,
        });
        await map.scrollIntoViewIfNeeded();
        const originalPoint = await map.evaluate((svg) => {
          const point = svg.querySelector("circle:nth-of-type(2)");
          if (!point) return null;
          const position = new DOMPoint(
            Number(point.getAttribute("cx")),
            Number(point.getAttribute("cy")),
          ).matrixTransform(point.getScreenCTM());
          return { x: position.x, y: position.y };
        });
        const markers = workspace.getByRole("button", {
          name: /^Select .+ on circuit$/,
        });
        const markerCount = await markers.count();
        let markerFocus;
        if (mode === "baseline") {
          assert.equal(markerCount, 0);
          assert.ok(originalPoint);
          await page.mouse.click(originalPoint.x, originalPoint.y);
          assert.equal(
            await workspace
              .getByRole("button", { name: "Jamie Brooks", exact: true })
              .getAttribute("aria-pressed"),
            "false",
          );
        } else {
          assert.equal(markerCount, 3);
          const marker = workspace.getByRole("button", {
            name: "Select Jamie Brooks on circuit",
            exact: true,
          });
          if (touch) await marker.tap();
          else await marker.click();
          assert.equal(
            await workspace
              .getByRole("button", { name: "Jamie Brooks", exact: true })
              .getAttribute("aria-pressed"),
            "true",
          );
          await marker.focus();
          await page.keyboard.press("Space");
          assert.equal(await marker.getAttribute("aria-pressed"), "false");
          await page.keyboard.press("Enter");
          assert.equal(await marker.getAttribute("aria-pressed"), "true");
          markerFocus = await marker.evaluate((element) => {
            const style = getComputedStyle(element);
            return {
              width: style.outlineWidth,
              style: style.outlineStyle,
              color: style.outlineColor,
            };
          });
          assert.equal(markerFocus.width, "2px");
          assert.equal(markerFocus.style, "solid");
          await workspace
            .getByRole("button", {
              name: "Clear driver selection",
              exact: true,
            })
            .click();
          assert.equal(await marker.getAttribute("aria-pressed"), "false");
          await map.evaluate((element) =>
            element.scrollIntoView({ behavior: "instant", block: "center" }),
          );
          await marker.click();
        }
        const list = workspace.getByRole("button", {
          name: "Jamie Brooks",
          exact: true,
        });
        const mapBox = await map.boundingBox(),
          listBox = await list.boundingBox();
        if (motion === "no-preference")
          await page.screenshot({ path: resolve(output, label + ".png") });
        const measurements = {
          markerCount,
          mapBox,
          listBox,
          listDistanceBelowMap: listBox.y - (mapBox.y + mapBox.height),
          input: touch ? "touchscreen" : "mouse",
          markerFocus,
        };
        if (mode === "final") {
          const selection = workspace.getByLabel("Map selection", {
            exact: true,
          });
          assert.match(await selection.innerText(), /Jamie Brooks/);
          await workspace
            .getByRole("button", { name: "Alex Rivera", exact: true })
            .click();
          assert.equal(
            await workspace
              .getByRole("button", {
                name: "Select Alex Rivera on circuit",
                exact: true,
              })
              .getAttribute("aria-pressed"),
            "true",
          );
          await workspace.locator('input[type="file"]').setInputFiles({
            name: "original-qa-capture.ndjson",
            mimeType: "application/json",
            buffer: Buffer.from(capture),
          });
          await workspace
            .getByText("Local capture · Source and layout unverified", {
              exact: true,
            })
            .waitFor();
          const qaMarker = workspace.getByRole("button", {
            name: "Select QA Driver A on circuit",
            exact: true,
          });
          await qaMarker.scrollIntoViewIfNeeded();
          const alignment = await qaMarker.evaluate((button) => {
            const svg = button.parentElement.querySelector("svg");
            const point = new DOMPoint(35, 25).matrixTransform(
              svg.querySelector("g").getScreenCTM(),
            );
            const rect = button.getBoundingClientRect();
            return {
              xError: Math.abs(point.x - (rect.x + rect.width / 2)),
              yError: Math.abs(point.y - (rect.y + rect.height / 2)),
              width: rect.width,
              height: rect.height,
            };
          });
          assert.ok(
            alignment.xError < 1 && alignment.yError < 1,
            "Marker aligns to independently transformed source coordinates",
          );
          assert.ok(alignment.width >= 44 && alignment.height >= 44);
          await qaMarker.click();
          await workspace
            .getByRole("button", { name: "Next snapshot", exact: true })
            .click();
          assert.equal(
            await markers.count(),
            0,
            "Missing and off-map samples create no misleading map control",
          );
          assert.match(await selection.innerText(), /Position unavailable/);
          await workspace
            .getByRole("button", { name: "Next snapshot", exact: true })
            .click();
          assert.match(await selection.innerText(), /absent/);
          await workspace
            .getByRole("button", { name: "Next snapshot", exact: true })
            .click();
          await workspace
            .getByRole("button", { name: "QA Driver B", exact: true })
            .click();
          await workspace
            .getByRole("button", { name: "QA Driver A", exact: true })
            .click();
          assert.equal(
            await workspace
              .getByRole("button", {
                name: "Select QA Driver A on circuit",
                exact: true,
              })
              .getAttribute("aria-pressed"),
            "true",
            "List still resolves overlapping positions",
          );
          await series.selectOption("IndyCar");
          await workspace
            .getByText("Circuit map unavailable", { exact: true })
            .waitFor();
          assert.equal(
            await workspace
              .getByLabel("Map selection", { exact: true })
              .count(),
            0,
          );
          Object.assign(measurements, {
            alignment,
            staticMotion: motion,
            sourceFailuresTruthful: true,
          });
        }
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth + 1,
          ),
          false,
        );
        assert.deepEqual(errors, []);
        assert.deepEqual(failedResources, []);
        results.push({
          label,
          passed: true,
          seriesOptions,
          measurements,
          errors,
          consoleEntries,
          failedResources,
          blockedExternal,
        });
        console.log(`${mode} ${label}: passed`);
      } finally {
        await context.close();
      }
    }
  }
  const hashes = {};
  for (const file of [
    "projects/f1-predictions/website/src/components/ui/CircuitReplayWorkspace.tsx",
    "projects/f1-predictions/website/src/lib/replayStream.ts",
    "projects/f1-predictions/website/src/lib/replayStreamDemo.ts",
    "projects/f1-predictions/website/out/circuits.html",
    "scripts/qa/circuit_selection.mjs",
  ])
    hashes[file] = createHash("sha256")
      .update(await readFile(resolve(root, file)))
      .digest("hex");
  await writeFile(
    resolve(output, "summary.json"),
    JSON.stringify(
      { mode, browser: browser.version(), results, hashes },
      null,
      2,
    ) + "\n",
  );
} finally {
  await browser.close();
  await new Promise((done) => server.close(done));
}
