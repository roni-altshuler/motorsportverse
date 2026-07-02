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
// Managed-dir files that are legitimately site-specific — never synced.
const SITE_SPECIFIC = new Set(["ui/DriverHeadshot.tsx"]);

const check = process.argv.includes("--check");
let drifted = 0;
let synced = 0;

function manage(rel) {
  if (SITE_SPECIFIC.has(rel)) return;
  const src = join(CANONICAL, rel);
  if (!existsSync(src)) return;
  const want = readFileSync(src, "utf8");
  for (const targetRoot of TARGETS) {
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
