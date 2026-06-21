/**
 * loadTrustStats — server-only, build-time assembler for the honest
 * credibility numbers shown on the marketing layer.
 *
 * Reads the JSON that the Python pipeline already writes under
 * `public/data/` directly off disk at build time (this module is imported
 * only by the home `page.tsx` server component, never by a client bundle —
 * `node:fs`/`node:path` would break a client import).
 *
 * Every read is defensive: a missing or malformed file degrades that group to
 * `null` so the static export never fails, and the consuming components skip
 * the section rather than render a fabricated number.
 *
 * Honesty rule (CLAUDE.md): backtest and current-season figures are kept in
 * structurally separate groups and never combined into one headline number.
 */
import fs from "node:fs";
import path from "node:path";

import type { TrustStats } from "@/types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

function readJson<T>(...segments: string[]): T | null {
  try {
    const raw = fs.readFileSync(path.join(DATA_DIR, ...segments), "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

interface BenchmarkAggregate {
  rounds?: number;
  mae?: number;
  within_3_rate?: number;
  podium_hit_rate?: number;
  winner_hit_rate?: number;
  ndcg_at_5?: number;
}

interface BenchmarkSummary {
  seasons?: number[];
  aggregate?: Record<string, BenchmarkAggregate>;
  headlineVariant?: string;
  headlineMaeImprovement?: number;
}

interface HistoricalBacktestSummary {
  totalRows?: number;
}

interface GpAccuracyReport {
  generatedAt?: string;
  overallAccuracy?: {
    seasonAccuracyPct?: number;
    roundsWithActual?: number;
    seasonMeanError?: number;
  };
}

function loadBacktest(): TrustStats["backtest"] {
  const bench = readJson<BenchmarkSummary>("benchmark", "summary.json");
  const hist = readJson<HistoricalBacktestSummary>(
    "historical_backtest",
    "summary.json",
  );
  if (!bench?.aggregate || !bench.headlineVariant) return null;
  const headline = bench.aggregate[bench.headlineVariant];
  if (!headline || typeof headline.mae !== "number") return null;

  return {
    rounds: headline.rounds ?? 0,
    seasons: bench.seasons ?? [],
    maePositions: headline.mae,
    within3Rate: headline.within_3_rate ?? 0,
    podiumHitRate: headline.podium_hit_rate ?? 0,
    winnerHitRate: headline.winner_hit_rate ?? 0,
    ndcgAt5: headline.ndcg_at_5 ?? 0,
    maeImprovementVsBaseline: bench.headlineMaeImprovement ?? 0,
    gradedRows: hist?.totalRows ?? 0,
  };
}

function loadCurrentSeason(): {
  current: TrustStats["currentSeason"];
  generatedAt: string | null;
} {
  const report = readJson<GpAccuracyReport>("gp_accuracy_report.json");
  const overall = report?.overallAccuracy;
  if (!overall) return { current: null, generatedAt: report?.generatedAt ?? null };
  return {
    current: {
      accuracyPct: overall.seasonAccuracyPct ?? null,
      roundsGraded: overall.roundsWithActual ?? 0,
      meanError: overall.seasonMeanError ?? null,
    },
    generatedAt: report?.generatedAt ?? null,
  };
}

/** Assemble the full TrustStats object at build time. Never throws. */
export function loadTrustStats(): TrustStats {
  const { current, generatedAt } = loadCurrentSeason();
  return {
    backtest: loadBacktest(),
    currentSeason: current,
    provenance: { generatedAt },
  };
}
