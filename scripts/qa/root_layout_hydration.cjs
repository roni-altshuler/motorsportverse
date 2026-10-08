// Diagnostic only: compile the actual RootLayout; stub unrelated shell imports.
// This models one pending Flight child, not a captured production root cause.
const fs = require("node:fs"),
  Module = require("node:module"),
  path = require("node:path"),
  crypto = require("node:crypto");
const root = process.cwd();
const requireSite = Module.createRequire(root + "/package.json");
const load = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === "react") request = "next/dist/compiled/react";
  if (request === "react/jsx-runtime")
    request = "next/dist/compiled/react/jsx-runtime";
  if (request === "next/dist/compiled/scheduler")
    request = "next/dist/compiled/scheduler/unstable_mock";
  if (request === "next/font/local")
    return { default: () => ({ variable: "diagnostic-font" }) };
  if (request === "next/navigation") return { usePathname: () => "/circuits" };
  if (request.endsWith("globals.css")) return {};
  if (request === "@/lib/SeasonProvider")
    return { SeasonProvider: ({ children }) => children };
  if (request === "@/lib/season") return { DEFAULT_SEASON_YEAR: 2026 };
  if (
    [
      "@/components/Navbar",
      "@/components/Footer",
      "@/components/race-weekend/LiveContextBand",
    ].includes(request)
  )
    return { __esModule: true, default: () => null };
  if (request === "@/components/SmoothScrollProvider")
    return compiledSmooth.exports;
  if (request === "@/components/RouteMain") return compiledMain.exports;
  return load.call(this, request, parent, isMain);
};
const React = requireSite("next/dist/compiled/react"),
  Scheduler = requireSite("next/dist/compiled/scheduler/unstable_mock");
const ts = requireSite("typescript"),
  { JSDOM } = requireSite("jsdom");
function compile(filename) {
  const source = fs.readFileSync(filename, "utf8"),
    m = new Module(filename, module);
  m.filename = filename;
  m.paths = Module._nodeModulePaths(path.dirname(filename));
  const compiledSource =
    process.argv.includes("--without-child-boundary") &&
    filename.endsWith("/RouteMain.tsx")
      ? source.replace("<RouteContent>{children}</RouteContent>", "{children}")
      : source;
  m._compile(
    ts.transpileModule(compiledSource, {
      compilerOptions: {
        jsx: ts.JsxEmit.ReactJSX,
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
      },
    }).outputText,
    filename,
  );
  return { exports: m.exports, source, compiledSource };
}
const compiledSmooth = compile(
  root + "/src/components/SmoothScrollProvider.tsx",
);
const compiledMain = compile(root + "/src/components/RouteMain.tsx");
const compiledLayout = compile(root + "/src/app/layout.tsx");
const { renderToString } = requireSite("next/dist/compiled/react-dom/server");
const h = React.createElement,
  content = h(
    React.Suspense,
    { fallback: null },
    h("section", { id: "diagnostic-content" }, "Original synthetic page"),
  );
const app = (child) => compiledLayout.exports.default({ children: child });
const markup = renderToString(app(content));
const serverMarkup = process.argv.includes("--different-server-text")
  ? markup.replace("Original synthetic page", "Different server fixture")
  : markup;
const dom = new JSDOM(serverMarkup, {
  url: "http://localhost/motorsportverse/projects/f1/circuits",
});
for (const key of [
  "window",
  "document",
  "Node",
  "Element",
  "HTMLElement",
  "Text",
  "Comment",
  "DocumentFragment",
  "Event",
  "CustomEvent",
  "MutationObserver",
  "HTMLIFrameElement",
])
  global[key] = dom.window[key];
window.matchMedia = () => ({
  matches: true,
  addEventListener() {},
  removeEventListener() {},
});
window.scrollTo = () => {};
const originalMain = document.querySelector("main"),
  originalContent = document.querySelector("#diagnostic-content");
const errors = [],
  listeners = [],
  chunk = {
    status: "pending",
    value: null,
    then(resolve) {
      listeners.push(resolve);
    },
  };
const lazy = {
  $$typeof: Symbol.for("react.lazy"),
  _payload: chunk,
  _init(payload) {
    Scheduler.log("read:" + payload.status);
    if (payload.status === "fulfilled") return payload.value;
    throw payload;
  },
};
const { hydrateRoot } = requireSite("next/dist/compiled/react-dom/client");
Module._load = load;
(async () => {
  React.startTransition(() =>
    hydrateRoot(document, app(lazy), {
      onRecoverableError(error) {
        errors.push({ message: error.message, stack: error.stack });
      },
    }),
  );
  await Promise.resolve();
  Scheduler.unstable_flushNumberOfYields(1);
  const pendingLog = Scheduler.unstable_clearLog();
  chunk.status = "fulfilled";
  chunk.value = content;
  listeners.forEach((resolve) => resolve(content));
  Scheduler.unstable_flushAllWithoutAsserting();
  await Promise.resolve();
  Scheduler.unstable_flushAllWithoutAsserting();
  console.log(
    JSON.stringify(
      {
        react: React.version,
        route: "/motorsportverse/projects/f1/circuits",
        reducedMotion: true,
        matchingMarkup: serverMarkup === renderToString(app(content)),
        withoutChildBoundary: process.argv.includes("--without-child-boundary"),
        serverMarkupSha256: crypto
          .createHash("sha256")
          .update(serverMarkup)
          .digest("hex"),
        sourceSha256: crypto
          .createHash("sha256")
          .update(compiledLayout.source)
          .digest("hex"),
        routeMainSha256: crypto
          .createHash("sha256")
          .update(compiledMain.source)
          .digest("hex"),
        compiledMainSha256: crypto
          .createHash("sha256")
          .update(compiledMain.compiledSource)
          .digest("hex"),
        shellImportsStubbed: true,
        actualSmoothScrollProvider: true,
        pendingLog,
        settledLog: Scheduler.unstable_clearLog(),
        errors,
        mainReused: document.querySelector("main") === originalMain,
        contentReused:
          document.querySelector("#diagnostic-content") === originalContent,
      },
      null,
      2,
    ),
  );
  dom.window.close();
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
