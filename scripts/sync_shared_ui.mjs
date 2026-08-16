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
  join(ROOT, "projects/motogp-predictions/website/src/components"),
  join(ROOT, "projects/wrc-predictions/website/src/components"),
  join(ROOT, "projects/wec-predictions/website/src/components"),
  join(ROOT, "projects/imsa-predictions/website/src/components"),
  // The ecosystem hub. Its copies were already byte-identical to canonical —
  // simply ungated, which is how it came to carry a number-ticker failsafe that
  // canonical lacked for months. An ungated identical copy is not a copy that
  // stays identical; it is one nobody has diffed yet.
  join(ROOT, "website/src/components"),
];

// Files a specific target legitimately diverges on, with the reason. Anything
// not listed here must match canonical exactly.
const TARGET_EXEMPTIONS = {
  // The hub's bento grid uses the card-pop treatment from the ecosystem
  // landing design; the series sites use the flat variant. Deliberate.
  "website/src/components": new Set(["magicui/bento-grid.tsx"]),
};

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
// Files every site must carry, created in a target that lacks them.
//
// INTERSECT_DIRS deliberately will not push a canonical-only file, on the
// reasoning that a site may simply not use it. That is right for a chart and
// wrong for these: they are the honesty primitives. `format.ts` is what makes
// an absent value render as an em dash instead of a confident 0, and the
// evidence components are what put a baseline next to an accuracy claim. A
// site that quietly lacks them does not degrade gracefully — it publishes a
// number with nothing next to it, which is the failure mode the whole
// evidence discipline exists to prevent. So they are pushed, not intersected.
const REQUIRED_FILES = [
  "ui/format.ts",
  "ui/EvidencePanel.tsx",
  "ui/BaselineLadder.tsx",
  "ui/EmptyState.tsx",
  "ui/StatusBanner.tsx",
  "ui/Skeleton.tsx",
];
// The shared component tests travel with the components they pin. A site that
// carried the components but not their tests would pass CI while rendering a
// suppressed losing comparison.
const REQUIRED_TEST_DIR = "src/__tests__/shared";
// Shared loaders that live under src/lib rather than src/components. Managed
// against the site root, like the tests.
const REQUIRED_SRC_FILES = ["src/lib/evidence.ts"];
// Managed-dir files that are legitimately site-specific — never synced.
const SITE_SPECIFIC = new Set(["ui/DriverHeadshot.tsx"]);

const check = process.argv.includes("--check");
let drifted = 0;
let synced = 0;

function manage(rel, { required = false, canonicalRoot = CANONICAL, targetRoots = TARGETS } = {}) {
  if (SITE_SPECIFIC.has(rel)) return;
  const src = join(canonicalRoot, rel);
  if (!existsSync(src)) return;
  const want = readFileSync(src, "utf8");
  for (const targetRoot of targetRoots) {
    const key = targetRoot.replace(ROOT + "/", "");
    if (TARGET_EXEMPTIONS[key]?.has(rel)) continue;
    const dst = join(targetRoot, rel);
    if (!existsSync(dst)) {
      // A required file missing from a site is drift, not an opt-out.
      if (!required) continue;
      if (check) {
        console.error(`MISSING: ${dst.replace(ROOT + "/", "")} — required shared file is absent`);
        drifted++;
        continue;
      }
      mkdirSync(dirname(dst), { recursive: true });
      writeFileSync(dst, want);
      console.log(`created ${dst.replace(ROOT + "/", "")}`);
      synced++;
      continue;
    }
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
for (const rel of REQUIRED_FILES) manage(rel, { required: true });

// The shared tests live one level up from components/, so they are managed
// against the site src/ root rather than the components root.
const CANONICAL_SRC = join(ROOT, "projects/f1-predictions/website");
const TARGET_SRCS = TARGETS.map((t) => dirname(dirname(t)));
const testBase = join(CANONICAL_SRC, REQUIRED_TEST_DIR);
if (existsSync(testBase)) {
  for (const f of readdirSync(testBase)) {
    manage(join(REQUIRED_TEST_DIR, f), {
      required: true,
      canonicalRoot: CANONICAL_SRC,
      targetRoots: TARGET_SRCS,
    });
  }
}
for (const rel of REQUIRED_SRC_FILES) {
  manage(rel, { required: true, canonicalRoot: CANONICAL_SRC, targetRoots: TARGET_SRCS });
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
