#!/usr/bin/env node
// Shared-UI sync: the F1 flagship's ui/ + magicui/ primitives and the four
// series-agnostic charts are the CANONICAL copies; the F2/F3 sites carry
// committed duplicates (each site is an independent static-export build, so a
// real npm workspace package would touch every install + the deploy assembler
// — highest-risk, lowest payoff; committed copies + this drift gate are the
// pragmatic contract instead).
//
//   node scripts/sync_shared_ui.mjs           # copy canonical -> F2/F3 trees
//   node scripts/sync_shared_ui.mjs --check   # exit 1 if any copy drifted
//
// Only files present in the canonical set are managed; site-specific extras
// (e.g. F2/F3's DriverHeadshot.tsx) are left alone. Files listed in
// SITE_SPECIFIC are excluded from management entirely. All shared components
// must style through CSS custom properties (var(--accent…)) — never hardcode
// a series color — so one source renders correctly under every site's tokens.
import { readFileSync, writeFileSync, existsSync, readdirSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const CANONICAL = join(ROOT, "projects/f1-predictions/website/src/components");
const TARGETS = [
  join(ROOT, "projects/f2-predictions/website/src/components"),
  join(ROOT, "projects/f3-predictions/website/src/components"),
  join(ROOT, "projects/formula-e-predictions/website/src/components"),
  join(ROOT, "projects/nascar-predictions/website/src/components"),
  join(ROOT, "projects/indycar-predictions/website/src/components"),
  // The ecosystem hub carries the same ui/ + magicui/ primitives and was
  // already byte-identical — it was simply never gated, so nothing would have
  // caught the day it drifted. Its own components (ProjectCard, MaturityBadge,
  // …) live outside these directories and are untouched by the sync.
  join(ROOT, "website/src/components"),
];

// Directories synced wholesale (every canonical file is managed).
const SHARED_DIRS = ["magicui"];
// Directories where only the canonical files that ALSO exist in the target
// are managed (targets may carry extras; canonical-only files are not pushed
// because the target site may not use them at all).
const INTERSECT_DIRS = ["ui"];
// Individual files managed by exact path. NOTE: the chart components
// (FinishProbabilityHeatmap, HeadToHeadMatrix, PodiumProbabilityChart,
// ProgressionChart) are deliberately NOT here — the F2/F3 variants were
// adapted (different type modules, headshot resolvers, props), so they are
// per-site code, not drifted copies. Only add a chart once its data contract
// is genuinely series-agnostic.
const SHARED_FILES = [];
// Managed-dir files that are legitimately site-specific — never synced anywhere.
const SITE_SPECIFIC = new Set(["ui/DriverHeadshot.tsx"]);

// Per-target exemptions: `<target substring>` -> files that target owns.
// Narrower than SITE_SPECIFIC, which drops a file from the gate on EVERY site;
// this keeps the file gated everywhere except where the divergence is
// deliberate. An exemption needs a reason on the line above it — an unexplained
// one is indistinguishable from drift somebody gave up on.
const TARGET_EXEMPTIONS = {
  // The hub's hover language is `card-pop` (cinematic catalog), not the series
  // sites' `hover-lift-premium` (instrument). Both classes exist in the hub's
  // globals.css; this is a design decision, not drift. See DESIGN.md §0.
  "website/src/components": new Set(["magicui/bento-grid.tsx"]),
};

function exempt(rel, targetRoot) {
  for (const [needle, files] of Object.entries(TARGET_EXEMPTIONS)) {
    if (targetRoot.includes(needle) && files.has(rel)) return true;
  }
  return false;
}

const check = process.argv.includes("--check");
let drifted = 0;
let synced = 0;

function manage(rel, canonicalRoot = CANONICAL, targetRoots = TARGETS) {
  if (SITE_SPECIFIC.has(rel)) return;
  const src = join(canonicalRoot, rel);
  if (!existsSync(src)) return;
  const want = readFileSync(src, "utf8");
  for (const targetRoot of targetRoots) {
    if (exempt(rel, targetRoot)) continue;
    const dst = join(targetRoot, rel);
    if (!existsSync(dst)) continue; // target site doesn't carry this file
    const have = readFileSync(dst, "utf8");
    if (have === want) continue;
    if (check) {
      console.error(`DRIFT: ${dst.replace(ROOT + "/", "")} differs from canonical F1 copy`);
      drifted++;
    } else {
      mkdirSync(dirname(dst), { recursive: true });
      writeFileSync(dst, want);
      console.log(`synced ${dst.replace(ROOT + "/", "")}`);
      synced++;
    }
  }
}

for (const dir of [...SHARED_DIRS, ...INTERSECT_DIRS]) {
  const base = join(CANONICAL, dir);
  if (!existsSync(base)) continue;
  for (const f of readdirSync(base)) manage(join(dir, f));
}
for (const rel of SHARED_FILES) manage(rel);

// The shared components carry shared TESTS. They are gated for the same reason
// the components are: a site whose copy of the evidence tests quietly diverged
// would go green while no longer checking the rule the test names. The suites
// under __tests__/shared/ import only from components/ui/, so they run
// unchanged on every site.
const CANONICAL_TESTS = join(
  ROOT,
  "projects/f1-predictions/website/src/__tests__/shared",
);
const TEST_TARGETS = TARGETS.map((components) =>
  join(dirname(components), "__tests__/shared"),
);
if (existsSync(CANONICAL_TESTS)) {
  for (const f of readdirSync(CANONICAL_TESTS)) {
    manage(f, CANONICAL_TESTS, TEST_TARGETS);
  }
}

if (check) {
  if (drifted) {
    console.error(
      `\n${drifted} shared component(s) drifted. Run: node scripts/sync_shared_ui.mjs\n` +
        `(edit the canonical copy under projects/f1-predictions/website/src/components/)`,
    );
    process.exit(1);
  }
  console.log("shared UI in sync ✓");
} else {
  console.log(synced ? `${synced} file(s) synced` : "nothing to sync — already identical");
}
