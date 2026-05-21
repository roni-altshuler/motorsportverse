/**
 * convert-viz-to-webp.ts (B-P0.3)
 *
 * Walks `public/visualizations/<round>/**\/*.png` and creates a `.webp`
 * sibling for each PNG using sharp.  Idempotent — skips files that are
 * newer than their PNG source.
 *
 * Runs during `prebuild` (alongside the OG-image generator) so the
 * static export ships both PNG and WebP for every visualization tile.
 * The race-detail page uses `<picture>` to prefer WebP, falling back to
 * PNG when the browser can't decode it.
 *
 * Sharp ships transitively with Next.js (next@16 → sharp@0.34); no new
 * dependency to install.
 *
 * Compression policy
 * ------------------
 * - WebP quality 82 — visually indistinguishable from the source PNG
 *   for matplotlib charts (no fine detail to preserve); typical 60-75%
 *   size reduction.
 * - AVIF skipped for v1: encoding is ~10x slower and the size win over
 *   WebP for plot output is small.  Add later if Lighthouse asks for it.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");
const VIZ_ROOT = path.join(ROOT, "public", "visualizations");

const WEBP_QUALITY = 82;

interface ConvertStats {
  scanned: number;
  converted: number;
  skipped: number;
  errors: number;
  bytesIn: number;
  bytesOut: number;
}

function findPngs(dir: string, out: string[]): void {
  if (!fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      findPngs(full, out);
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".png")) {
      out.push(full);
    }
  }
}

async function convertOne(
  pngPath: string,
  stats: ConvertStats,
): Promise<void> {
  const webpPath = pngPath.replace(/\.png$/i, ".webp");
  stats.scanned += 1;
  try {
    const pngStat = fs.statSync(pngPath);
    let webpStat: fs.Stats | null = null;
    try {
      webpStat = fs.statSync(webpPath);
    } catch {
      webpStat = null;
    }
    // Skip if existing WebP is newer than the PNG — idempotent re-runs
    // don't redo work.
    if (webpStat && webpStat.mtimeMs > pngStat.mtimeMs) {
      stats.skipped += 1;
      return;
    }
    const t0 = Date.now();
    const info = await sharp(pngPath)
      .webp({ quality: WEBP_QUALITY, effort: 4 })
      .toFile(webpPath);
    stats.converted += 1;
    stats.bytesIn += pngStat.size;
    stats.bytesOut += info.size;
    const ms = Date.now() - t0;
    const rel = path.relative(VIZ_ROOT, pngPath);
    const ratio = ((info.size / pngStat.size) * 100).toFixed(0);
    console.log(`[webp] ${rel.padEnd(40)} ${(pngStat.size / 1024).toFixed(0)}KB → ${(info.size / 1024).toFixed(0)}KB (${ratio}%) ${ms}ms`);
  } catch (err) {
    stats.errors += 1;
    console.warn(`[webp] FAILED ${pngPath}: ${err}`);
  }
}

async function main(): Promise<void> {
  const pngs: string[] = [];
  findPngs(VIZ_ROOT, pngs);
  if (pngs.length === 0) {
    console.log(`[webp] No PNGs under ${path.relative(ROOT, VIZ_ROOT)}; nothing to do.`);
    return;
  }
  console.log(`[webp] Converting ${pngs.length} PNGs from ${path.relative(ROOT, VIZ_ROOT)} (quality ${WEBP_QUALITY})`);

  const stats: ConvertStats = {
    scanned: 0,
    converted: 0,
    skipped: 0,
    errors: 0,
    bytesIn: 0,
    bytesOut: 0,
  };

  // Sequential — sharp is single-threaded per call but Node's libuv pool
  // is fine.  For 148 files, sequential adds maybe 5-8s total; not worth
  // the complexity of a worker pool.
  for (const png of pngs) {
    await convertOne(png, stats);
  }

  console.log(
    `[webp] Done. scanned=${stats.scanned}  converted=${stats.converted}  skipped=${stats.skipped}  errors=${stats.errors}`
  );
  if (stats.converted > 0) {
    const ratio = ((stats.bytesOut / stats.bytesIn) * 100).toFixed(0);
    console.log(
      `[webp] Total ${(stats.bytesIn / 1024).toFixed(0)}KB → ${(stats.bytesOut / 1024).toFixed(0)}KB (${ratio}% of source)`
    );
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
