// Screenshot harness for the Chrome Valley Racing League website
// (MotorsportVerse). Serves the static export in ./out and captures
// desktop + mobile shots of each route, so visual regressions and broken
// components are caught after a build.
//
//   npm run build
//   npm i -D playwright && npx playwright install chromium   # one-time
//   node scripts/shoot.mjs [outdir]
//
// Default output: /tmp/chrome-valley-shots (kept out of the repo). Mirrors
// the ecosystem sites' scripts/shoot.mjs pattern.

import { createServer } from "node:http";
import { readFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, extname } from "node:path";
import { chromium } from "playwright";

const ROOT = new URL("..", import.meta.url).pathname;
const OUT = join(ROOT, "out");
const SHOTS = process.argv[2] || "/tmp/chrome-valley-shots";
const PORT = 4341;

const MIME = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

function serve() {
  return createServer(async (req, res) => {
    try {
      const p = decodeURIComponent(req.url.split("?")[0]);
      let file = join(OUT, p);
      if (p.endsWith("/")) file = join(file, "index.html");
      if (!existsSync(file) && existsSync(file + ".html")) file = file + ".html";
      if (!existsSync(file) && existsSync(join(file, "index.html")))
        file = join(file, "index.html");
      const data = await readFile(file);
      res.writeHead(200, {
        "content-type": MIME[extname(file)] || "application/octet-stream",
      });
      res.end(data);
    } catch {
      res.writeHead(404);
      res.end("not found");
    }
  });
}

// trailingSlash: true in next.config → every route is /route/index.html.
const ROUTES = [
  ["home", "/"],
  ["garage", "/garage/"],
  ["season", "/season/"],
];

const server = serve();
await new Promise((r) => server.listen(PORT, r));
const browser = await chromium.launch();
await mkdir(SHOTS, { recursive: true });

for (const [vp, width, height] of [
  ["desktop", 1440, 900],
  ["mobile", 390, 844],
]) {
  const ctx = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 1,
  });
  const page = await ctx.newPage();
  for (const [name, route] of ROUTES) {
    await page.goto(`http://localhost:${PORT}${route}`, { waitUntil: "networkidle" });
    // Scroll through so any lazy work settles, then return to the top
    // before capturing (no smooth-scroll library on this site).
    const total = await page.evaluate(() => document.body.scrollHeight);
    for (let y = 0; y <= total; y += 600) {
      await page.mouse.wheel(0, 600);
      await page.waitForTimeout(50);
    }
    await page.waitForTimeout(400);
    await page.mouse.wheel(0, -total - 2000);
    await page.waitForTimeout(600);
    const out = join(SHOTS, `${name}__${vp}.png`);
    await page.screenshot({ path: out, fullPage: true });
    console.log("shot", out);
  }
  await ctx.close();
}

await browser.close();
server.close();
console.log("done →", SHOTS);
