// Actual local exports and navigation. Public URLs are not contacted: only the
// Live demo link's origin is substituted with this server, preserving its path.
import { chromium } from "../projects/f1-predictions/website/node_modules/playwright/index.mjs";
import { createServer } from "node:http";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { resolve, extname } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";
import { waitForRouteReady } from "./lib/route_readiness.mjs";
const root = fileURLToPath(new URL("../", import.meta.url)),
  base = "/motorsportverse",
  output = resolve(process.argv[2] || "/tmp/motorsport-theme-journeys"),
  mode = process.argv[3] || "baseline";
await mkdir(output, { recursive: true });
const series = [
  "f1",
  "f2",
  "f3",
  "formula-e",
  "nascar",
  "indycar",
  "motogp",
  "wrc",
  "wec",
  "imsa",
].filter(
  (site) => !process.argv[4] || process.argv[4].split(",").includes(site),
);
assert.ok(series.length > 0, "Choose at least one known series");
assert.ok(["baseline", "final"].includes(mode), "Choose baseline or final QA");
const sites = [
  { site: "hub", prefix: base, dir: resolve(root, "website") },
  ...series.map((site) => ({
    site,
    prefix: base + "/projects/" + site,
    dir: resolve(root, "projects/" + site + "-predictions/website"),
  })),
];
const mime = {
  ".html": "text/html",
  ".txt": "text/plain",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".png": "image/png",
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
  ".ico": "image/x-icon",
};
const server = createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(
        new URL(req.url, "http://localhost").pathname,
      ),
      s = [...sites]
        .reverse()
        .find(
          (s) => pathname === s.prefix || pathname.startsWith(s.prefix + "/"),
        );
    if (!s) throw new Error("no site");
    const path = pathname.slice(s.prefix.length) || "/",
      out = resolve(s.dir, "out");
    let f = resolve(out, "." + path);
    if (!f.startsWith(out + "/") && f !== out) throw new Error("path");
    let bytes;
    try {
      bytes = await readFile(f);
    } catch {
      const choices = extname(f)
        ? []
        : [f.replace(/\/$/, "") + ".html", resolve(f, "index.html")];
      for (const candidate of choices) {
        try {
          bytes = await readFile(candidate);
          f = candidate;
          break;
        } catch {}
      }
    }
    if (!bytes) {
      f = resolve(out, "404.html");
      try {
        bytes = await readFile(f);
      } catch {
        f = resolve(out, "404/index.html");
        bytes = await readFile(f);
      }
      res.statusCode = 404;
    }
    res.setHeader(
      "Content-Type",
      mime[extname(f)] || "application/octet-stream",
    );
    res.end(req.method === "HEAD" ? undefined : bytes);
  } catch {
    res.writeHead(404);
    res.end("Not found");
  }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));
const origin = "http://127.0.0.1:" + server.address().port;
const browser = await chromium.launch({
  executablePath: "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const req = createRequire(resolve(root, "website/package.json")),
  ts = req("typescript"),
  React = req("react"),
  render = req("react-dom/server").renderToStaticMarkup;
function fallback(file) {
  const text = readFileSync(file, "utf8"),
    code = ts.transpileModule(text, {
      compilerOptions: {
        jsx: ts.JsxEmit.ReactJSX,
        module: ts.ModuleKind.CommonJS,
      },
    }).outputText;
  const module = { exports: {} };
  new Function("require", "module", "exports", code)(
    req,
    module,
    module.exports,
  );
  return render(
    React.createElement(module.exports.default, {
      error: Object.assign(new Error("Synthetic QA fallback"), {
        digest: "QA-ONLY",
      }),
      reset: () => {},
    }),
  );
}
const appError = fallback(resolve(root, "website/src/app/error.tsx")),
  globalError = fallback(resolve(root, "website/src/app/global-error.tsx"));
const failures = [],
  results = [];
function rgb(value) {
  const v = value.match(/[\d.]+/g)?.map(Number);
  return v && v.length >= 3 ? v : null;
}
function luminance(c) {
  return c
    .slice(0, 3)
    .map((v) => {
      v /= 255;
      return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    })
    .reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
}
function contrast(fg, bg) {
  const a = rgb(fg),
    b = rgb(bg);
  if (!a || !b) return null;
  if (a.length > 3)
    for (let i = 0; i < 3; i++) a[i] = a[i] * a[3] + b[i] * (1 - a[3]);
  const x = luminance(a),
    y = luminance(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}
function check(condition, label) {
  if (!condition) failures.push(label);
}
const contracts = new Map();
async function routeContract(page, path, state = "ready") {
  const clean = path.replace(/\/$/, "");
  const key = clean + ":" + state;
  if (contracts.has(key)) return contracts.get(key);
  const s = [...sites]
    .reverse()
    .find((s) => clean === s.prefix || clean.startsWith(s.prefix + "/"));
  assert.ok(s, "Unknown expected destination: " + path);
  const route = clean.slice(s.prefix.length) || "/";
  const json = (file) =>
    JSON.parse(readFileSync(resolve(s.dir, "public/data", file), "utf8"));
  const mainDataFiles = {
    f1: "season",
    f2: "f2",
    f3: "f3",
    "formula-e": "fe",
    nascar: "nascar",
    indycar: "indycar",
    motogp: "motogp",
    wrc: "wrc",
  };
  const data = mainDataFiles[s.site]
    ? json(mainDataFiles[s.site] + ".json")
    : null;
  let expected = {
    path: clean,
    headings: [],
    text: [],
    selectors: [],
    basis: "actual destination static export",
  };
  if (route.startsWith("/race/")) {
    const round = Number(route.split("/")[2]);
    const snapshot = json(
      "rounds/round_" + String(round).padStart(2, "0") + ".json",
    );
    const title =
      s.site === "f1" ? snapshot.name : snapshot.raceName || snapshot.venueName;
    expected.headings = [{ level: s.site === "f1" ? 1 : 3, text: title }];
    expected.text = [
      s.site === "f1"
        ? snapshot.circuit
        : "Round " + String(round).padStart(2, "0"),
    ];
    expected.basis = "stored round identity for " + round;
  } else if (/^\/(driver|rider)\//.test(route)) {
    const code = decodeURIComponent(route.split("/")[2]).toUpperCase();
    const driver = (data.drivers ?? data.driverStandings).find(
      (d) => d.code === code,
    );
    assert.ok(driver, "No stored profile identity for " + path);
    expected.headings = [
      { level: 1, text: driver.fullName ?? driver.name },
      { level: 3, text: "Championship points" },
      { level: 3, text: "Predicted vs actual finish" },
    ];
    expected.basis = "stored " + s.site + " profile identity " + code;
  } else if (route === "/standings" && data) {
    const year =
      s.site === "formula-e"
        ? `${data.season - 1}-${String(data.season).slice(2)}`
        : String(data.season);
    expected.headings = [{ level: 1, text: year + " Standings" }];
    const standing =
      s.site === "f1"
        ? json("standings.json").drivers[0]
        : data.driverStandings[0];
    expected.text = [standing.driverFullName ?? standing.name];
    expected.basis = "stored season and leading standings identity";
  } else if (route === "/calendar" && s.site === "f1") {
    expected.headings = [{ level: 1, text: "Season Calendar" }];
    expected.selectors = [
      `a[href="${s.prefix}/race/${data.calendar[0].round}"]`,
    ];
    expected.basis = "calendar destination and stored first round link";
  } else if (route === "/accuracy" && s.site === "f1") {
    expected.headings = [
      { level: 1, text: "Prediction Accuracy" },
      { level: 2, text: "Evidence" },
      { level: 2, text: "How Accuracy Is Measured" },
    ];
    expected.basis = "loaded accuracy dashboard and evidence sections";
  } else {
    const missing = /\/(qa-missing-page|not-a-real-page)$/.test(route);
    const relative = missing ? "/404" : route;
    let html;
    for (const f of [
      relative === "/" ? "index.html" : relative.slice(1) + ".html",
      relative.slice(1) + "/index.html",
    ]) {
      try {
        html = await readFile(resolve(s.dir, "out", f), "utf8");
        break;
      } catch {}
    }
    assert.ok(html, "No production export for expected route " + path);
    expected.headings = await page.evaluate((html) => {
      const doc = new DOMParser().parseFromString(html, "text/html");
      return [doc.querySelector("main h1"), doc.querySelector("main h2")]
        .filter(Boolean)
        .map((el) => {
          const copy = el.cloneNode(true);
          copy
            .querySelectorAll('img, svg, [role="img"], [aria-hidden="true"]')
            .forEach((image) => image.remove());
          return {
            level: Number(el.tagName[1]),
            text: copy.textContent.replace(/\s+/g, " ").trim(),
          };
        });
    }, html);
    if (route === "/" && s.site === "f1")
      expected.headings.push({ level: 2, text: "Where the season stands" });
  }
  if (route === "/compare/laps") {
    const texts = {
      loading: "Loading the 2025 Monaco timing snapshot…",
      error: "load and verify this archive",
      empty:
        "This archive has fewer than two drivers with complete, consistent lap timings.",
      ready: "Driver A",
    };
    expected.text.push(texts[state]);
    expected.loadingFixture = state === "loading";
  }
  if (route === "/circuits") {
    const texts = {
      empty: "Circuit map unavailable",
      demo: "Clear capture",
      loading: "Opening capture…",
      error: "Capture unavailable",
    };
    if (texts[state]) expected.text.push(texts[state]);
    expected.loadingFixture = state === "loading";
  }
  assert.ok(
    expected.headings.length,
    "No destination heading contract for " + path,
  );
  contracts.set(key, expected);
  return expected;
}
async function appearance(page, label, path, state = "ready") {
  const readiness = await waitForRouteReady(
    page,
    await routeContract(page, path, state),
  );
  const value = await page.evaluate(() => {
    const b = getComputedStyle(document.body),
      h = getComputedStyle(document.documentElement),
      heading = document.querySelector("main h1");
    return {
      url: location.pathname,
      background: b.backgroundColor,
      ink: b.color,
      bodyFont: b.fontFamily,
      headingFont: heading ? getComputedStyle(heading).fontFamily : null,
      canvas: h.getPropertyValue("--canvas").trim(),
      accent: h.getPropertyValue("--accent-f1-red").trim(),
      colorScheme: h.colorScheme,
      metaScheme:
        document.querySelector('meta[name="color-scheme"]')?.content ?? null,
      theme: document.documentElement.dataset.theme ?? null,
      ambient: document.documentElement.dataset.ambient ?? null,
      scrollWidth: document.documentElement.scrollWidth,
      width: innerWidth,
      mainLandmarks: document.querySelectorAll("main").length,
      firstStyledFrame: window.__firstStyledFrame,
      overflowCandidates: [...document.querySelectorAll("body *")]
        .flatMap((el) => {
          const rect = el.getBoundingClientRect(),
            style = getComputedStyle(el);
          return rect.right > innerWidth + 1 &&
            rect.width > 0 &&
            style.visibility !== "hidden" &&
            style.display !== "none"
            ? [
                {
                  tag: el.tagName,
                  class:
                    typeof el.className === "string" ? el.className : "svg",
                  text: el.textContent.trim().slice(0, 70),
                  right: rect.right,
                  width: rect.width,
                  position: style.position,
                  transform: style.transform,
                },
              ]
            : [];
        })
        .slice(0, 20),
    };
  });
  check(value.scrollWidth <= value.width, label + ": overflow");
  check(
    value.metaScheme === "dark" && value.theme === "dark",
    label + ": dark appearance declaration",
  );
  check(
    value.firstStyledFrame?.background === value.background,
    label + ": first styled frame canvas drift",
  );
  return { label, readiness, ...value };
}
async function pointerLink(page, anchor) {
  await anchor.evaluate((el) =>
    el.scrollIntoView({
      behavior: "instant",
      block: "center",
      inline: "nearest",
    }),
  );
  const initial = await anchor.evaluate((el) => {
    const rect = el.getBoundingClientRect();
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
  });
  await page.mouse.move(initial.x, initial.y);
  const element = await anchor.elementHandle();
  assert.ok(element, "Actual navigation link exists");
  const hit = await page.waitForFunction(
    (el) => {
      const rect = el.getBoundingClientRect();
      const x = rect.x + rect.width / 2,
        y = rect.y + rect.height / 2;
      return rect.width > 0 &&
        rect.height > 0 &&
        document.elementFromPoint(x, y)?.closest("a") === el
        ? { x, y }
        : false;
    },
    element,
    { timeout: 15000, polling: "raf" },
  );
  const point = await hit.jsonValue();
  await hit.dispose();
  await element.dispose();
  // Use real pointer input at the verified hit target. Navbar subpixel motion
  // need not meet Playwright's exact rectangle-equality actionability check.
  await page.mouse.click(point.x, point.y);
}
async function link(page, path) {
  await page.bringToFront();
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.waitForFunction(() => Math.abs(scrollY) <= 1);
  const normal = (p) => p.replace(/\/$/, "");
  let openedMenu = false;
  async function visibleLink() {
    const candidates = openedMenu
      ? page
          .getByRole("dialog", { name: "Mobile navigation", exact: true })
          .locator("a[href]")
      : page.locator("a[href]");
    for (let i = 0; i < (await candidates.count()); i++) {
      const a = candidates.nth(i),
        href = await a.getAttribute("href");
      if (
        href &&
        normal(new URL(href, page.url()).pathname) === normal(path) &&
        (await a.isVisible())
      )
        return a;
    }
  }
  const mobileMenu = page.getByRole("button", {
    name: "Open menu",
    exact: true,
  });
  if (page.viewportSize().width < 768 && (await mobileMenu.isVisible())) {
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await page.waitForFunction(() => Math.abs(scrollY) <= 1);
    await mobileMenu.click();
    openedMenu = true;
    await page
      .getByRole("dialog", { name: "Mobile navigation", exact: true })
      .waitFor();
  }
  let found = await visibleLink();
  if (!found) {
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await page.waitForFunction(() => Math.abs(scrollY) <= 1);
    const mobile = page.getByRole("button", { name: "Open menu", exact: true });
    if (await mobile.isVisible()) {
      await mobile.click();
      openedMenu = true;
    } else
      await page.getByRole("button", { name: "Races", exact: true }).hover();
    await page
      .locator('a[href="' + path + '"]')
      .first()
      .waitFor({ state: "visible" });
    found = await visibleLink();
  }
  assert.ok(found, "No actual visible link to " + path);
  await pointerLink(page, found);
  await page.waitForURL((url) => normal(url.pathname) === normal(path));
  if (openedMenu)
    await page
      .getByRole("dialog", { name: "Mobile navigation", exact: true })
      .waitFor({ state: "hidden", timeout: 3000 });
  await waitForRouteReady(page, await routeContract(page, path));
}
async function firstMainLink(page, prefix, optional = false) {
  const anchors = page.locator("main a[href]");
  for (let i = 0; i < (await anchors.count()); i++) {
    const a = anchors.nth(i),
      href = await a.getAttribute("href");
    if (
      href &&
      new URL(href, page.url()).pathname.startsWith(prefix) &&
      (await a.isVisible())
    ) {
      const path = new URL(href, page.url()).pathname;
      await pointerLink(page, a);
      await page.waitForURL(
        (u) => u.pathname.replace(/\/$/, "") === path.replace(/\/$/, ""),
      );
      await waitForRouteReady(page, await routeContract(page, path));
      return path;
    }
  }
  if (optional) return null;
  throw new Error("No main navigation link for " + prefix);
}
async function rootFallbackMetrics(page, html) {
  return page.evaluate(
    (html) =>
      new Promise((resolve) => {
        const frame = document.createElement("iframe");
        frame.title = "QA-only actual global-error fallback";
        frame.style.width = "100%";
        frame.style.height = "400px";
        frame.onload = () => {
          const doc = frame.contentDocument,
            body = frame.contentWindow.getComputedStyle(doc.body),
            digest = doc.querySelector("p:last-of-type");
          const result = {
            background: body.backgroundColor,
            ink: body.color,
            font: body.fontFamily,
            digestColor: frame.contentWindow.getComputedStyle(digest).color,
          };
          frame.remove();
          resolve(result);
        };
        frame.srcdoc = html;
        document.body.append(frame);
      }),
    html,
  );
}
async function colorMetrics(locator) {
  return locator.evaluate((el) => {
    const c = getComputedStyle(el);
    let p = el,
      bg = "rgb(0, 0, 0)";
    while (p) {
      const b = getComputedStyle(p).backgroundColor;
      if (b !== "rgba(0, 0, 0, 0)" && b !== "transparent") {
        bg = b;
        break;
      }
      p = p.parentElement;
    }
    return {
      text: el.textContent.trim().slice(0, 100),
      color: c.color,
      background: bg,
      font: c.fontFamily,
      size: c.fontSize,
      border: c.borderTopWidth,
      padding: c.padding,
      outline: c.outlineColor,
      outlineWidth: c.outlineWidth,
    };
  });
}
async function shot(page, name, fullPage = true) {
  await page.mouse.move(page.viewportSize().width - 2, 200);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.waitForFunction(() => Math.abs(scrollY) <= 1);
  await page.evaluate(
    () =>
      new Promise((done) =>
        requestAnimationFrame(() => requestAnimationFrame(done)),
      ),
  );
  await page.screenshot({
    path: resolve(output, name + ".png"),
    fullPage,
  });
}
try {
  const cases = (
    mode === "baseline"
      ? [["desktop-light", { width: 1440, height: 1000 }, "light"]]
      : [
          ["desktop-light", { width: 1440, height: 1000 }, "light"],
          ["desktop-dark", { width: 1440, height: 1000 }, "dark"],
          ["mobile-light", { width: 390, height: 844 }, "light"],
          ["mobile-dark", { width: 390, height: 844 }, "dark"],
        ]
  ).filter(([label]) => !process.argv[5] || process.argv[5] === label);
  assert.ok(cases.length > 0, "Choose at least one known viewport case");
  for (const [label, viewport, colorScheme] of cases) {
    console.log(label + ": journey");
    const context = await browser.newContext({
        viewport,
        colorScheme,
        reducedMotion: label.endsWith("light") ? "reduce" : "no-preference",
      }),
      pages = [],
      pageErrors = [],
      blockedExternal = [],
      httpFailures = [];
    context.on("page", (p) => {
      pages.push(p);
      p.on("pageerror", (e) =>
        pageErrors.push({ url: p.url(), error: e.message }),
      );
      p.on("response", (r) => {
        if (r.status() >= 400)
          httpFailures.push({
            url: r.url().replace(origin, ""),
            status: r.status(),
          });
      });
    });
    await context.route("**/*", async (route) => {
      const u = new URL(route.request().url());
      if (u.origin !== origin) {
        blockedExternal.push(u.href);
        await route.abort();
      } else await route.continue();
    });
    await context.addInitScript(() => {
      const originalFetch = window.fetch;
      window.__qaPendingFetch = 0;
      window.fetch = function (...args) {
        const url = new URL(
          args[0] instanceof Request ? args[0].url : String(args[0]),
          location.href,
        );
        const local = url.origin === location.origin;
        if (local) window.__qaPendingFetch++;
        return originalFetch.apply(this, args).finally(() => {
          if (local) window.__qaPendingFetch--;
        });
      };
      const record = () => {
        if (document.body) {
          const c = getComputedStyle(document.body);
          if (
            getComputedStyle(document.documentElement)
              .getPropertyValue("--canvas")
              .trim()
          ) {
            window.__firstStyledFrame = {
              background: c.backgroundColor,
              ink: c.color,
              theme: document.documentElement.dataset.theme ?? null,
              ambient: document.documentElement.dataset.ambient ?? null,
            };
            return;
          }
        }
        requestAnimationFrame(record);
      };
      requestAnimationFrame(record);
    });
    const hub = await context.newPage();
    await hub.goto(origin + base + "/", { waitUntil: "networkidle" });
    const journey = [await appearance(hub, "hub home", base)];
    if (label === "desktop-light" || label === "mobile-light")
      await shot(hub, label + "-hub-home");
    const caption = await colorMetrics(hub.locator(".race-feed-note").first());
    caption.contrast = contrast(caption.color, caption.background);
    check(
      caption.contrast >= 4.5,
      label + ": hub caption contrast " + caption.contrast,
    );
    await hub.getByRole("searchbox").fill("qa-only-no-matching-race");
    await hub.getByText("No races in this view.", { exact: true }).waitFor();
    journey.push(await appearance(hub, "hub empty search", base));
    await hub.getByRole("searchbox").fill("");
    await hub.getByRole("button", { name: "off", exact: true }).first().click();
    await link(hub, base + "/projects");
    journey.push(await appearance(hub, "hub directory", base + "/projects"));
    await link(hub, base + "/docs");
    journey.push(await appearance(hub, "hub docs", base + "/docs"));
    await hub.goBack();
    journey.push(await appearance(hub, "hub back", base + "/projects"));
    await hub.goForward();
    journey.push(await appearance(hub, "hub forward", base + "/docs"));
    await hub.reload({ waitUntil: "networkidle" });
    journey.push(await appearance(hub, "hub reload", base + "/docs"));
    check(
      journey.slice(2).every((x) => x.ambient === "off"),
      label + ": ambient navigation/reload",
    );
    await link(hub, base + "/projects");
    const launch = [],
      seriesJourneys = [];
    for (const site of series) {
      const slug =
        site === "formula-e" ? "formula-e-predictions" : site + "-predictions";
      await link(hub, base + "/projects/" + slug);
      const detail = await appearance(
          hub,
          "hub " + site + " detail",
          base + "/projects/" + slug,
        ),
        demo = hub.getByRole("link", { name: "Live demo", exact: true });
      const metric = await colorMetrics(demo);
      metric.contrast = contrast(metric.color, metric.background);
      launch.push({ site, ...metric });
      check(
        metric.contrast >= 4.5,
        label + ": " + site + " launch contrast " + metric.contrast,
      );
      if (
        (site === "f2" && label === "desktop-light") ||
        (site === "nascar" && label === "mobile-light")
      )
        await shot(hub, label + "-" + site + "-launch");
      const original = await demo.getAttribute("href");
      assert.equal(
        new URL(original).pathname,
        base + "/projects/" + site + "/",
      );
      await demo.evaluate((a, origin) => {
        a.href = origin + new URL(a.href).pathname;
      }, origin);
      const popupPromise = hub.waitForEvent("popup");
      await demo.click();
      const p = await popupPromise;
      await p.bringToFront();
      await p.waitForLoadState("networkidle");
      const sp = base + "/projects/" + site,
        walk = [await appearance(p, site + " home", sp)];
      await link(p, sp + "/calendar");
      walk.push(await appearance(p, site + " calendar", sp + "/calendar"));
      const multiClass = ["wec", "imsa"].includes(site);
      const race = await firstMainLink(
        p,
        sp + (multiClass ? "/round/" : "/race/"),
        true,
      );
      walk.push(
        await appearance(
          p,
          site + (race ? " race" : " calendar without published race links"),
          race || sp + "/calendar",
        ),
      );
      await link(p, sp + "/standings");
      walk.push(await appearance(p, site + " standings", sp + "/standings"));
      let profile = null;
      if (site === "f1") {
        const driversLink = p
          .getByRole("link", {
            name: "Drivers",
            exact: true,
            includeHidden: true,
          })
          .first();
        const href = await driversLink.getAttribute("href");
        assert.ok(href, "F1 exposes its Drivers profile navigation");
        profile = new URL(href, p.url()).pathname;
        await link(p, profile);
      } else
        profile = await firstMainLink(
          p,
          sp +
            (multiClass
              ? "/entry/"
              : site === "motogp"
                ? "/rider/"
                : "/driver/"),
          true,
        );
      if (profile) {
        walk.push(await appearance(p, site + " profile", profile));
        if (["f1", "motogp"].includes(site) && label.endsWith("light"))
          await shot(p, label + "-" + site + "-profile", false);
      } else
        assert.ok(
          false,
          site +
            " has exported profiles; a published profile link must be exercised",
        );
      await link(p, sp + "/accuracy");
      walk.push(await appearance(p, site + " evidence", sp + "/accuracy"));
      await p.goBack();
      walk.push(
        await appearance(p, site + " back", profile || sp + "/standings"),
      );
      await p.goForward();
      walk.push(await appearance(p, site + " forward", sp + "/accuracy"));
      await p.reload({ waitUntil: "networkidle" });
      walk.push(await appearance(p, site + " reload", sp + "/accuracy"));
      await link(p, sp + "/about");
      walk.push(await appearance(p, site + " about", sp + "/about"));
      const footer = p
        .locator("footer p, footer span")
        .filter({ hasText: "©" })
        .first();
      let caption = null;
      if (await footer.count()) {
        caption = await colorMetrics(footer);
        caption.contrast = contrast(caption.color, caption.background);
        check(
          caption.contrast >= 4.5,
          label + ": " + site + " footer contrast " + caption.contrast,
        );
      }
      const rootFallback = await rootFallbackMetrics(
        p,
        fallback(
          resolve(
            root,
            "projects/" +
              site +
              "-predictions/website/src/app/global-error.tsx",
          ),
        ),
      );
      rootFallback.digestContrast = contrast(
        rootFallback.digestColor,
        rootFallback.background,
      );
      check(
        rootFallback.digestContrast >= 4.5,
        label +
          ": " +
          site +
          " global-error digest contrast " +
          rootFallback.digestContrast,
      );
      check(
        rootFallback.background === walk[0].background,
        label + ": " + site + " global-error canvas",
      );
      check(
        walk.every(
          (x) =>
            x.background === walk[0].background &&
            x.ink === walk[0].ink &&
            x.bodyFont === walk[0].bodyFont &&
            x.accent === walk[0].accent,
        ),
        label + ": " + site + " palette/font drift",
      );
      if (site === "f1") {
        await link(p, sp + "/compare/laps");
        await p
          .getByRole("combobox", { name: "Driver A", exact: true })
          .waitFor();
        walk.push(
          await appearance(p, "f1 lap comparison", sp + "/compare/laps"),
        );
        await p
          .getByRole("combobox", { name: "Driver A", exact: true })
          .selectOption("VER");
        if (label === "desktop-light") await shot(p, label + "-lap");
        const archive = "**/session-comparison/2025_Monaco_R.json";
        let release;
        const delayed = async (route) => {
          await new Promise((done) => (release = done));
          await route.continue();
        };
        await p.route(archive, delayed);
        await p.reload({ waitUntil: "domcontentloaded" });
        await p
          .getByText("Loading the 2025 Monaco timing snapshot…", {
            exact: true,
          })
          .waitFor();
        walk.push(
          await appearance(
            p,
            "f1 lap loading (QA delayed local response)",
            sp + "/compare/laps",
            "loading",
          ),
        );
        if (label === "desktop-light") await shot(p, label + "-lap-loading");
        release();
        await p
          .getByRole("combobox", { name: "Driver A", exact: true })
          .waitFor();
        await p.unroute(archive, delayed);
        const failed = (route) =>
          route.fulfill({ status: 503, body: "QA-only archive failure" });
        await p.route(archive, failed);
        await p.reload({ waitUntil: "networkidle" });
        await p
          .getByRole("alert")
          .filter({ hasText: "load and verify this archive" })
          .waitFor();
        walk.push(
          await appearance(
            p,
            "f1 lap error (QA local 503)",
            sp + "/compare/laps",
            "error",
          ),
        );
        if (label === "mobile-light") await shot(p, label + "-lap-error");
        await p.unroute(archive, failed);
        await p.getByRole("button", { name: "Try again", exact: true }).click();
        await p
          .getByRole("combobox", { name: "Driver A", exact: true })
          .waitFor();
        const emptyFixture = JSON.parse(
          await readFile(
            resolve(
              root,
              "projects/f1-predictions/website/public/data/session-comparison/2025_Monaco_R.json",
            ),
            "utf8",
          ),
        );
        emptyFixture.drivers = [];
        const empty = (route) =>
          route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(emptyFixture),
          });
        await p.route(archive, empty);
        await p.reload({ waitUntil: "networkidle" });
        await p
          .getByText(
            "This archive has fewer than two drivers with complete, consistent lap timings.",
            { exact: true },
          )
          .waitFor();
        walk.push(
          await appearance(
            p,
            "f1 lap empty (QA-only zero-driver fixture)",
            sp + "/compare/laps",
            "empty",
          ),
        );
        await p.unroute(archive, empty);
        await p.reload({ waitUntil: "networkidle" });
        await p
          .getByRole("combobox", { name: "Driver A", exact: true })
          .waitFor();
        await link(p, sp + "/circuits");
        await p.getByText("Circuit map unavailable", { exact: true }).waitFor();
        walk.push(
          await appearance(p, "f1 circuit empty", sp + "/circuits", "empty"),
        );
        await p
          .getByRole("button", { name: "Try fictional demo", exact: true })
          .click();
        await p.getByRole("img", { name: "Fictional circuit view" }).waitFor();
        walk.push(
          await appearance(p, "f1 circuit demo", sp + "/circuits", "demo"),
        );
        if (label === "mobile-light") await shot(p, label + "-circuit");
        await p
          .getByRole("button", { name: "Clear capture", exact: true })
          .click();
        await p.evaluate(() => {
          window.__originalFileText = File.prototype.text;
          File.prototype.text = async function () {
            await new Promise((done) => (window.__releaseFileText = done));
            return window.__originalFileText.call(this);
          };
        });
        await p.locator("input[type=file]").setInputFiles({
          name: "qa-delayed.ndjson",
          mimeType: "application/x-ndjson",
          buffer: Buffer.from("{"),
        });
        await p.getByText("Opening capture…", { exact: true }).waitFor();
        walk.push(
          await appearance(
            p,
            "f1 circuit loading (QA delayed File.text)",
            sp + "/circuits",
            "loading",
          ),
        );
        await p
          .getByRole("button", { name: "Cancel import", exact: true })
          .click();
        await p.evaluate(() => {
          window.__releaseFileText();
          File.prototype.text = window.__originalFileText;
        });
        await p
          .getByRole("button", { name: "Try fictional demo", exact: true })
          .waitFor();
        await p.locator("input[type=file]").setInputFiles({
          name: "qa-invalid.ndjson",
          mimeType: "application/x-ndjson",
          buffer: Buffer.from("{"),
        });
        await p
          .getByRole("region", { name: "Circuit workspace", exact: true })
          .getByRole("alert")
          .waitFor();
        walk.push(
          await appearance(p, "f1 circuit error", sp + "/circuits", "error"),
        );
      }
      if (
        (site === "f2" && label === "desktop-light") ||
        (site === "nascar" && label === "mobile-light")
      )
        await shot(p, label + "-" + site + "-about");
      await p.goto(origin + sp + "/qa-missing-page", {
        waitUntil: "networkidle",
      });
      walk.push(
        await appearance(p, site + " actual 404", sp + "/qa-missing-page"),
      );
      check(
        (await p.locator("main").count()) === 1,
        label + ": " + site + " duplicate 404 main",
      );
      await p
        .getByRole("link", { name: "Back to the season", exact: true })
        .click();
      await p.waitForURL((u) => u.pathname.replace(/\/$/, "") === sp);
      walk.push(await appearance(p, site + " 404 return", sp));
      await p
        .locator("main")
        .first()
        .evaluate(
          (el, html) => {
            el.innerHTML = html;
          },
          fallback(
            resolve(
              root,
              "projects/" + site + "-predictions/website/src/app/error.tsx",
            ),
          ),
        );
      check(
        (await p.locator("main").count()) === 1,
        label + ": " + site + " duplicate error main",
      );
      const routeError = await colorMetrics(
        p.getByRole("button", { name: "Try again", exact: true }),
      );
      check(
        parseFloat(routeError.border) > 0,
        label + ": " + site + " unstyled error action",
      );
      seriesJourneys.push({
        site,
        originalLaunchUrl: original,
        localLaunchUrl: p.url(),
        detail,
        walk,
        footer: caption,
        rootFallback,
        routeError,
        raceDetailAvailable: Boolean(race),
        profileDetailAvailable: Boolean(profile),
        profilePath: profile,
        profileKind: multiClass
          ? "entry"
          : site === "motogp"
            ? "rider"
            : "driver",
      });
      console.log(label + ": " + site + " complete");
      await p.close();
      await link(hub, base + "/projects");
    }
    await hub.goto(origin + base + "/not-a-real-page", {
      waitUntil: "networkidle",
    });
    journey.push(
      await appearance(hub, "hub actual 404", base + "/not-a-real-page"),
    );
    const missing = await colorMetrics(
      hub.getByRole("link", { name: /Back to/ }).first(),
    );
    check(
      (await hub.locator("main").count()) === 1,
      label + ": duplicate 404 main",
    );
    if (label === "desktop-light") await shot(hub, label + "-404");
    await hub
      .getByRole("link", { name: /Back to/ })
      .first()
      .click();
    await hub.waitForURL((u) => u.pathname === base + "/");
    journey.push(await appearance(hub, "hub 404 return", base));
    // Explicit QA fixture: actual product fallback markup, rendered via React SSR,
    // inserted into the real hub shell. This does not prove boundary triggering.
    await hub
      .locator("main")
      .first()
      .evaluate((el, html) => {
        el.innerHTML = html;
      }, appError);
    const routeError = await colorMetrics(
      hub.getByRole("button", { name: "Try again", exact: true }),
    );
    check(parseFloat(routeError.border) > 0, label + ": unstyled error action");
    check(
      (await hub.locator("main").count()) === 1,
      label + ": duplicate error main",
    );
    if (label === "desktop-light") await shot(hub, label + "-route-error");
    const rootFallback = await rootFallbackMetrics(hub, globalError);
    rootFallback.digestContrast = contrast(
      rootFallback.digestColor,
      rootFallback.background,
    );
    check(
      rootFallback.digestContrast >= 4.5,
      label +
        ": hub global-error digest contrast " +
        rootFallback.digestContrast,
    );
    check(
      rootFallback.background === journey[0].background,
      label + ": global-error canvas differs",
    );
    await hub.reload({ waitUntil: "networkidle" });
    const restored = await appearance(hub, "hub restored", base);
    check(restored.ambient === "off", label + ": ambient restored");
    await hub.getByRole("button", { name: "off", exact: true }).first().focus();
    const focus = await colorMetrics(
      hub.getByRole("button", { name: "off", exact: true }).first(),
    );
    focus.contrast = contrast(focus.outline, focus.background);
    check(focus.contrast >= 3, label + ": focus contrast " + focus.contrast);
    const knownErrors = pageErrors.filter(
      (e) => !e.error.includes("Synthetic QA"),
    );
    check(
      knownErrors.length === 0,
      label + ": unexpected browser errors " + JSON.stringify(knownErrors),
    );
    const missingPortraits = httpFailures.filter(
      (r) => r.status === 404 && /\/headshots\/[\w-]+\.webp$/.test(r.url),
    );
    const unexpectedHttpFailures = httpFailures.filter(
      (r) =>
        !missingPortraits.includes(r) &&
        !(
          r.status === 503 &&
          r.url.endsWith("/session-comparison/2025_Monaco_R.json")
        ) &&
        !(
          r.status === 404 && /\/(not-a-real-page|qa-missing-page)$/.test(r.url)
        ),
    );
    check(
      unexpectedHttpFailures.length === 0,
      label +
        ": unexpected local HTTP failures " +
        JSON.stringify(unexpectedHttpFailures),
    );
    results.push({
      label,
      viewport,
      colorScheme,
      journey,
      caption,
      launch,
      seriesJourneys,
      missing,
      routeError,
      rootFallback,
      restored,
      focus,
      pageErrors,
      httpFailures,
      missingPortraits,
      unexpectedHttpFailures,
      blockedExternal: [...new Set(blockedExternal)],
      fixtures: [
        "local origin substitution for Live demo link",
        "React SSR product error fallback inserted in real hub shell",
        "isolated actual global-error markup iframe",
        "original malformed NDJSON",
        "delayed local archive response; local 503 response; QA-only zero-driver archive fixture",
        "delayed browser-local File.text, cancelled before malformed contents are parsed",
      ],
    });
    await context.close();
  }
  const sourceHash = {};
  for (const s of sites)
    for (const file of [
      "src/app/layout.tsx",
      "src/styles/tokens.css",
      "src/app/globals.css",
      "src/app/error.tsx",
      "src/app/not-found.tsx",
      "src/app/global-error.tsx",
      "src/lib/useReducedMotion.ts",
      "src/components/Navbar.tsx",
      "src/components/ui/HUDPanel.tsx",
    ])
      sourceHash[s.site + "/" + file] = createHash("sha256")
        .update(await readFile(resolve(s.dir, file)))
        .digest("hex");
  for (const file of ["src/lib/color.ts", "src/app/projects/[slug]/page.tsx"])
    sourceHash["hub/" + file] = createHash("sha256")
      .update(await readFile(resolve(root, "website", file)))
      .digest("hex");
  for (const site of ["f1", "motogp"])
    sourceHash[site + "/src/components/StandingsPage.tsx"] = createHash(
      "sha256",
    )
      .update(
        await readFile(
          resolve(
            root,
            "projects/" +
              site +
              "-predictions/website/src/components/StandingsPage.tsx",
          ),
        ),
      )
      .digest("hex");
  await writeFile(
    resolve(output, "journey-qa.json"),
    JSON.stringify(
      {
        mode,
        browser: browser.version(),
        node: process.version,
        clock:
          "Native browser time and animation timeline; no Playwright clock override.",
        runnerSha256: createHash("sha256")
          .update(await readFile(fileURLToPath(import.meta.url)))
          .digest("hex"),
        readinessHelperSha256: createHash("sha256")
          .update(
            await readFile(resolve(root, "scripts/lib/route_readiness.mjs")),
          )
          .digest("hex"),
        transport:
          "Local static exports at actual production base paths; no public deployment claim.",
        sourceHash,
        results,
        failures,
      },
      null,
      2,
    ) + "\n",
  );
  console.log(
    JSON.stringify({
      output,
      cases: results.length,
      sites: sites.length,
      failures,
    }),
  );
  if (mode === "final" && failures.length) process.exitCode = 1;
} finally {
  await browser.close();
  await new Promise((done) => server.close(done));
}
