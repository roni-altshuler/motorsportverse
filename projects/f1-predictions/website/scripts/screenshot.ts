/**
 * Screenshot harness for visual regression during the UI overhaul.
 *
 * Usage:
 *   npm run shoot -- <phase-label>
 *
 * Example:
 *   npm run shoot -- baseline
 *   npm run shoot -- phase-2-tokens
 *
 * Output: scripts/screenshots/<phase>/<route>__<variant>.png
 *
 * Variants per route:
 *   - desktop  : 1440x900
 *   - mobile   : 375x812
 *   - reduced  : 1440x900 with prefers-reduced-motion: reduce
 *
 * Boots `next dev` on port 3001 (avoiding common 3000 collision) and waits
 * for the first 200 before iterating. Kills the dev server on exit.
 */
import { chromium, type Browser, type Page } from "playwright";
import { spawn, type ChildProcess } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";

// Default 3001; override with SHOOT_PORT when something else already owns
// that port (the harness would otherwise screenshot the foreign server).
const PORT = Number(process.env.SHOOT_PORT ?? 3001);
const BASE = `http://localhost:${PORT}`;
const PHASE = process.argv[2] ?? "scratch";
const OUT_ROOT = path.resolve("scripts/screenshots", PHASE);

const ROUTES: { url: string; slug: string }[] = [
  { url: "/", slug: "home" },
  { url: "/calendar", slug: "calendar" },
  { url: "/standings", slug: "standings" },
  { url: "/race/1", slug: "race-r1" },
  { url: "/race/5", slug: "race-r5" },
  { url: "/accuracy", slug: "accuracy" },
  { url: "/about", slug: "about" },
  { url: "/design-system", slug: "design-system" },
];

async function waitForServer(url: string, timeoutMs = 60_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok || res.status === 404) return;
    } catch {
      // server not up yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Server did not respond on ${url} within ${timeoutMs}ms`);
}

async function shoot(
  browser: Browser,
  route: { url: string; slug: string },
  variant: "desktop" | "mobile" | "reduced",
): Promise<void> {
  const viewport =
    variant === "mobile" ? { width: 375, height: 812 } : { width: 1440, height: 900 };

  const context = await browser.newContext({
    viewport,
    reducedMotion: variant === "reduced" ? "reduce" : "no-preference",
  });
  const page: Page = await context.newPage();
  try {
    await page.goto(`${BASE}${route.url}`, { waitUntil: "networkidle", timeout: 30_000 });
    // wait for fonts
    await page.evaluate(() => {
      const docWithFonts = document as Document & {
        fonts?: { ready: Promise<unknown> };
      };
      return docWithFonts.fonts?.ready;
    });
    // brief settle for animations and intersection-observer hydration
    await page.waitForTimeout(variant === "reduced" ? 200 : 800);
    const filename = `${route.slug}__${variant}.png`;
    const out = path.join(OUT_ROOT, filename);
    await page.screenshot({ path: out, fullPage: true });
    console.log(`  shot ${route.url}  ->  ${path.relative(process.cwd(), out)}`);
  } catch (err) {
    console.warn(`  failed ${route.url} (${variant}): ${(err as Error).message}`);
  } finally {
    await context.close();
  }
}

async function main(): Promise<void> {
  await mkdir(OUT_ROOT, { recursive: true });

  console.log(`[shoot] phase=${PHASE} → ${OUT_ROOT}`);
  console.log("[shoot] starting next dev on :3001 ...");

  const child: ChildProcess = spawn("npx", ["next", "dev", "-p", String(PORT)], {
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, NODE_ENV: "development" },
  });

  // Surface fatal next-dev errors (helpful when build fails before first paint)
  child.stderr?.on("data", (chunk) => {
    const txt = chunk.toString();
    if (/error|failed/i.test(txt)) {
      process.stderr.write(`[next-dev] ${txt}`);
    }
  });

  const cleanup = () => {
    if (!child.killed) child.kill("SIGTERM");
  };
  process.on("exit", cleanup);
  process.on("SIGINT", () => {
    cleanup();
    process.exit(130);
  });

  try {
    await waitForServer(BASE, 90_000);
    console.log("[shoot] dev server ready, launching chromium ...");
    const browser = await chromium.launch({ headless: true });
    try {
      for (const route of ROUTES) {
        for (const variant of ["desktop", "mobile", "reduced"] as const) {
          await shoot(browser, route, variant);
        }
      }
    } finally {
      await browser.close();
    }
    console.log(`[shoot] done → ${OUT_ROOT}`);
  } finally {
    cleanup();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
