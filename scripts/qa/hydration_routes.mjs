// Local production-export diagnostics. Existing committed files only; external
// requests are blocked. Delivery/CPU controls are opt-in and never alter DOM.
import { chromium } from "../../projects/f1-predictions/website/node_modules/playwright/index.mjs";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { resolve, extname } from "node:path";
import { createHash } from "node:crypto";
const exported = resolve(process.argv[2]);
const output = resolve(process.argv[3]);
const repeats = Number(process.argv[4] || 12);
const base = "/motorsportverse/projects/f1";
await mkdir(output, { recursive: true });
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
const server = createServer(async (req, res) => {
  try {
    const path = decodeURIComponent(
      new URL(req.url, "http://localhost").pathname,
    );
    if (path === "/favicon.ico") {
      res.writeHead(204).end();
      return;
    }
    if (!path.startsWith(base)) throw Error("wrong base");
    const suffix = path.slice(base.length) || "/";
    let file = resolve(
      exported,
      `.${suffix.endsWith("/") ? suffix + "index.html" : suffix}`,
    );
    if (!file.startsWith(exported + "/")) throw Error("invalid path");
    let bytes;
    try {
      bytes = await readFile(file);
    } catch {
      if (extname(file)) throw Error("missing asset");
      try {
        file += ".html";
        bytes = await readFile(file);
      } catch {
        file = resolve(exported, `.${suffix}/index.html`);
        bytes = await readFile(file);
      }
    }
    if (
      process.env.HYDRATION_DIFFERENT_MARKUP === "1" &&
      suffix === "/circuits"
    ) {
      // Explicit negative-control server fixture, never a product/DOM mutation.
      bytes = Buffer.from(
        bytes
          .toString("utf8")
          .replace('<h1 class="display-xl">', '<h2 class="display-xl">')
          .replace("Explore the circuit.</h1>", "Explore the circuit.</h2>"),
      );
    }
    res.writeHead(200, {
      "Content-Type": mime[extname(file)] || "application/octet-stream",
    });
    const streamDelay = Number(process.env.HYDRATION_STREAM_DELAY || 0);
    if (streamDelay && extname(file) === ".html") {
      const text = bytes.toString("utf8");
      const chunks = [
        ...text.matchAll(/<script[^>]*>self\.__next_f\.push\(\[1,/g),
      ];
      if (chunks.length > 2) {
        const split = chunks[2].index;
        res.write(text.slice(0, split));
        setTimeout(() => res.end(text.slice(split)), streamDelay);
        return;
      }
    }
    res.end(bytes);
  } catch {
    res.writeHead(404).end("Not found");
  }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));
const origin =
  process.env.HYDRATION_ORIGIN || `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({
  executablePath: "/usr/bin/chromium",
  headless: true,
  args: ["--no-sandbox"],
});
const results = [];
let next = 0;
async function worker() {
  while (next < repeats) {
    const iteration = next++;
    const motion = iteration % 3 === 0 ? "no-preference" : "reduce";
    const viewport =
      iteration % 4 === 0
        ? { width: 1440, height: 1000 }
        : { width: 390, height: 844 };
    const delayScripts = iteration % 2 === 0 ? 0 : 120;
    console.log(
      JSON.stringify({
        iteration,
        motion,
        viewport,
        delayScripts,
        started: true,
      }),
    );
    const context = await browser.newContext({
      viewport,
      reducedMotion: motion,
    });
    const page = await context.newPage();
    let stage = "created";
    const errors = [],
      consoleErrors = [],
      requests = [],
      responses = [],
      navigation = [];
    await page.route("**/*", async (route) => {
      const req = route.request();
      if (!req.url().startsWith(origin)) return route.abort("blockedbyclient");
      if (delayScripts && req.resourceType() === "script")
        await new Promise((done) => setTimeout(done, delayScripts));
      return route.continue();
    });
    page.on("pageerror", (error) => {
      const event = {
        stage,
        route: new URL(page.url()).pathname,
        message: error.message,
        stack: error.stack,
        at: new Date().toISOString(),
      };
      errors.push(event);
      console.log(
        JSON.stringify({ iteration, motion, viewport, error: event }),
      );
    });
    page.on("console", (msg) => {
      if (msg.type() === "error")
        consoleErrors.push({ stage, message: msg.text() });
    });
    page.on("request", (req) =>
      requests.push({
        stage,
        url: req.url().replace(origin, ""),
        method: req.method(),
      }),
    );
    page.on("response", (res) => {
      if (res.status() >= 400 || res.request().headers()["rsc"])
        responses.push({
          stage,
          url: res.url().replace(origin, ""),
          status: res.status(),
          contentType: res.headers()["content-type"],
        });
    });
    page.on("framenavigated", (frame) => {
      if (frame === page.mainFrame())
        navigation.push({ stage, url: frame.url().replace(origin, "") });
    });
    const cdp = await context.newCDPSession(page);
    await cdp.send("Runtime.enable");
    const exceptions = [];
    cdp.on("Runtime.exceptionThrown", (event) =>
      exceptions.push({ stage, ...event.exceptionDetails }),
    );
    const cpuRate = Number(process.env.HYDRATION_CPU_RATE || 1);
    if (cpuRate > 1)
      await cdp.send("Emulation.setCPUThrottlingRate", { rate: cpuRate });
    const throwPoints = [];
    const pausedEvents = [];
    if (process.env.HYDRATION_THROW_OBSERVER === "1") {
      await cdp.send("Debugger.enable");
      cdp.on("Debugger.paused", async (event) => {
        try {
          const description = event.data?.description || "";
          pausedEvents.push({
            reason: event.reason,
            data: event.data,
            functionName: event.callFrames[0]?.functionName,
          });
          if (
            description.includes("418") ||
            description.includes("Hydration failed") ||
            event.callFrames[0]?.functionName === "rX"
          ) {
            const frames = [];
            for (const frame of event.callFrames.slice(0, 6)) {
              const scopes = [];
              for (const scope of frame.scopeChain.slice(0, 3)) {
                if (!scope.object.objectId) continue;
                const properties = await cdp.send("Runtime.getProperties", {
                  objectId: scope.object.objectId,
                  ownProperties: true,
                  generatePreview: true,
                });
                scopes.push({
                  type: scope.type,
                  properties: properties.result
                    .filter((p) => p.value)
                    .slice(0, 150)
                    .map((p) => ({
                      name: p.name,
                      type: p.value.type,
                      description: p.value.description,
                      preview: p.value.preview,
                      value: p.value.value,
                    })),
                });
              }
              frames.push({
                functionName: frame.functionName,
                url: frame.url,
                location: frame.location,
                scopes,
              });
            }
            const point = {
              stage,
              route: new URL(page.url()).pathname,
              motion,
              viewport,
              description,
              frames,
            };
            throwPoints.push(point);
            console.log(JSON.stringify({ iteration, throwPoint: point }));
          }
        } finally {
          await cdp.send("Debugger.resume").catch(() => {});
        }
      });
      await cdp.send("Debugger.setPauseOnExceptions", { state: "all" });
    }
    const ready = async () => {
      await page
        .getByRole("heading", { name: "Explore the circuit.", exact: true })
        .waitFor();
      await page
        .getByText("Circuit map unavailable", { exact: true })
        .waitFor();
    };
    try {
      stage = "hard-circuits";
      await page.goto(origin + base + "/circuits", {
        waitUntil: "networkidle",
      });
      await ready();
      stage = "hard-race12";
      await page.goto(origin + base + "/race/12", { waitUntil: "networkidle" });
      await page
        .getByRole("main")
        .getByRole("link", { name: "Circuit workspace", exact: true })
        .waitFor();
      stage = "soft-race12-to-circuits";
      await page
        .getByRole("main")
        .getByRole("link", { name: "Circuit workspace", exact: true })
        .click();
      await ready();
      await page.waitForLoadState("networkidle");
      stage = "reload-circuits";
      await page.reload({ waitUntil: "networkidle" });
      await ready();
      stage = "hard-race12-second";
      await page.goto(origin + base + "/race/12", { waitUntil: "networkidle" });
      await page
        .getByRole("main")
        .getByRole("link", { name: "Circuit workspace", exact: true })
        .waitFor();
      stage = "soft-race12-to-circuits-second";
      await page
        .getByRole("main")
        .getByRole("link", { name: "Circuit workspace", exact: true })
        .click();
      await ready();
      await page.waitForLoadState("networkidle");
    } catch (error) {
      errors.push({
        stage,
        route: page.url(),
        message: error.message,
        stack: error.stack,
        testFailure: true,
      });
    }
    const record = {
      iteration,
      motion,
      viewport,
      delayScripts,
      cpuRate,
      errors,
      consoleErrors,
      exceptions,
      throwPoints,
      pausedEvents,
      navigation,
      responses,
      requests,
    };
    results.push(record);
    await writeFile(
      resolve(output, `case-${iteration}.json`),
      JSON.stringify(record, null, 2) + "\n",
    );
    if (errors.length) {
      await writeFile(
        resolve(output, `case-${iteration}-recovered.html`),
        await page.content(),
      );
      await page.screenshot({
        path: resolve(output, `case-${iteration}.png`),
        fullPage: false,
      });
    }
    console.log(
      JSON.stringify({
        iteration,
        motion,
        viewport,
        delayScripts,
        errors: errors.length,
        hydrationErrors: errors.filter((e) => e.message.includes("418")).length,
      }),
    );
    await context.close();
  }
}
try {
  await Promise.all([worker(), worker()]);
} finally {
  await browser.close();
  await new Promise((done) => server.close(done));
}
const files = {};
for (const name of ["circuits.html", "race/12.html"])
  files[name] = createHash("sha256")
    .update(await readFile(resolve(exported, name)))
    .digest("hex");
const summary = {
  exported,
  origin,
  browser: "Chromium 151.0.7922.173",
  externalRequestsBlocked: true,
  nativeClock: true,
  domMutationsInjected: false,
  differentServerMarkupFixture: process.env.HYDRATION_DIFFERENT_MARKUP === "1",
  streamDelayMs: Number(process.env.HYDRATION_STREAM_DELAY || 0),
  files,
  results,
};
await writeFile(
  resolve(output, "summary.json"),
  JSON.stringify(summary, null, 2) + "\n",
);
console.log(
  JSON.stringify({
    cases: results.length,
    hydrationErrors: results
      .flatMap((x) => x.errors)
      .filter((e) => e.message.includes("418")).length,
    otherErrors: results
      .flatMap((x) => x.errors)
      .filter((e) => !e.message.includes("418")).length,
  }),
);
