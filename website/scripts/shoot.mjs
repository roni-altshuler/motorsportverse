// Screenshot harness for the MotorsportVerse ecosystem site.
// Serves the static export in ./out and captures desktop + mobile shots of each
// route, so visual regressions and broken components are caught after a build.
//
//   npm run build && node scripts/shoot.mjs [outdir]
//
// Default output: /tmp/mv-shots (kept out of the repo).

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, extname } from "node:path";
import { chromium } from "playwright";

const ROOT = new URL("..", import.meta.url).pathname;
const OUT = join(ROOT, "out");
const SHOTS = process.argv[2] || "/tmp/mv-shots";
const PORT = 4321;

const MIME = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".webp": "image/webp",
};

function serve() {
  return createServer(async (req, res) => {
    try {
      let p = decodeURIComponent(req.url.split("?")[0]);
      let file = join(OUT, p);
      if (p.endsWith("/")) file = join(file, "index.html");
      if (!existsSync(file) && existsSync(file + ".html")) file = file + ".html";
      if (!existsSync(file) && existsSync(join(file, "index.html"))) file = join(file, "index.html");
      const data = await readFile(file);
      res.writeHead(200, { "content-type": MIME[extname(file)] || "application/octet-stream" });
      res.end(data);
    } catch {
      res.writeHead(404);
      res.end("not found");
    }
  });
}

const ROUTES = [
  ["home", "/"],
  ["projects", "/projects/"],
  ["project-detail", "/projects/f1-predictions/"],
  ["project-detail-f2", "/projects/f2-predictions/"],
  ["docs", "/docs/"],
  ["contribute", "/contribute/"],
];

const server = serve();
await new Promise((r) => server.listen(PORT, r));
const browser = await chromium.launch();

const { mkdir } = await import("node:fs/promises");
await mkdir(SHOTS, { recursive: true });

for (const [vp, width, height] of [
  ["desktop", 1440, 900],
  ["mobile", 390, 844],
]) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  for (const [name, route] of ROUTES) {
    if (vp === "mobile" && !["home", "projects", "project-detail"].includes(name)) continue;
    await page.goto(`http://localhost:${PORT}${route}`, { waitUntil: "networkidle" });
    // Scroll through the page so IntersectionObserver-driven animations
    // (NumberTicker, reveals) fire, then return to top before capturing.
    await page.evaluate(async () => {
      const h = document.body.scrollHeight;
      for (let y = 0; y <= h; y += 600) {
        window.scrollTo(0, y);
        await new Promise((r) => setTimeout(r, 90));
      }
      window.scrollTo(0, 0);
      await new Promise((r) => setTimeout(r, 900));
    });
    await page.waitForTimeout(1100);
    const out = join(SHOTS, `${name}__${vp}.png`);
    await page.screenshot({ path: out, fullPage: true });
    console.log("shot", out);
  }
  await ctx.close();
}

await browser.close();
server.close();
console.log("done →", SHOTS);
