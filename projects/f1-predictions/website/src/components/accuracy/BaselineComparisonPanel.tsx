"use client";

import type { AccuracyBaselineBlock, GpAccuracyReportData } from "@/types";

/**
 * BaselineComparisonPanel — the honest scoreboard.
 *
 * Puts the model side-by-side with the naive strategies anyone could use
 * without a model: predict the finishing order to equal the qualifying grid,
 * predict the pole-sitter to win, predict the championship leader to win.
 * The best value in each column is highlighted regardless of which row owns
 * it — including when a baseline beats the model.
 *
 * Renders nothing when the season's `gp_accuracy_report.json` lacks the
 * `baselines` block (archived / pre-overhaul seasons).
 */

interface ScoreRow {
  key: string;
  name: string;
  description: string;
  isModel: boolean;
  winnerHits: number | null;
  roundsScored: number | null;
  winnerHitRate: number | null;
  podiumSetPct: number | null;
  pointsSetPct: number | null;
  blendPct: number | null;
  meanError: number | null;
}

function baselineRow(key: string, block: AccuracyBaselineBlock | undefined): ScoreRow | null {
  if (!block?.season) return null;
  const s = block.season;
  return {
    key,
    name: block.label,
    description: block.description,
    isModel: false,
    winnerHits: s.winnerHits ?? null,
    roundsScored: s.roundsScored ?? null,
    winnerHitRate: s.winnerHitRate ?? null,
    podiumSetPct: s.podiumSetPct ?? null,
    pointsSetPct: s.pointsSetPct ?? null,
    blendPct: s.blendPct ?? null,
    meanError: s.meanError ?? null,
  };
}

const fmtPct = (v: number | null) => (v == null ? "–" : `${v.toFixed(1)}%`);

export default function BaselineComparisonPanel({
  report,
}: {
  report: GpAccuracyReportData | null;
}) {
  const baselines = report?.baselines;
  const overall = report?.overallAccuracy;
  if (!baselines || !overall) return null;

  // Winner-hit tally for the model: prefer the explicit season fields, fall
  // back to counting per-round reports so slightly older data still renders.
  const gpReports = report?.gpReports ?? [];
  const modelWinnerHits =
    overall.seasonWinnerHits ?? (gpReports.length > 0 ? gpReports.filter((r) => r.winnerHit).length : null);
  const modelWinnerHitPct =
    overall.seasonWinnerHitPct ??
    (modelWinnerHits != null && overall.roundsWithActual > 0
      ? Number(((modelWinnerHits / overall.roundsWithActual) * 100).toFixed(1))
      : null);

  const modelRow: ScoreRow = {
    key: "model",
    name: "RaceIQ model",
    description: "Our published pre-race forecast, frozen after qualifying.",
    isModel: true,
    winnerHits: modelWinnerHits,
    roundsScored: overall.roundsWithActual ?? null,
    winnerHitRate: modelWinnerHitPct,
    podiumSetPct: overall.seasonPodiumAccuracyPct ?? null,
    pointsSetPct: overall.seasonPointsAccuracyPct ?? null,
    blendPct: overall.seasonAccuracyPct ?? null,
    meanError: overall.seasonMeanError ?? null,
  };

  const rows = [
    modelRow,
    baselineRow("gridOrder", baselines.gridOrder),
    baselineRow("poleSitter", baselines.poleSitter),
    baselineRow("pointsLeader", baselines.pointsLeader),
  ].filter((r): r is ScoreRow => r !== null);

  if (rows.length < 2) return null;

  // Column-wise winners. Higher is better for percentages; lower for error.
  const best = {
    winnerHitRate: Math.max(...rows.map((r) => r.winnerHitRate ?? -Infinity)),
    podiumSetPct: Math.max(...rows.map((r) => r.podiumSetPct ?? -Infinity)),
    pointsSetPct: Math.max(...rows.map((r) => r.pointsSetPct ?? -Infinity)),
    blendPct: Math.max(...rows.map((r) => r.blendPct ?? -Infinity)),
    meanError: Math.min(...rows.map((r) => r.meanError ?? Infinity)),
  };

  const cellStyle = (value: number | null, bestValue: number) => ({
    color: value != null && value === bestValue ? "var(--success)" : "var(--text)",
    fontWeight: value != null && value === bestValue ? 700 : 400,
  });

  const gridBeatsModelOnBlend =
    modelRow.blendPct != null &&
    baselines.gridOrder?.season.blendPct != null &&
    baselines.gridOrder.season.blendPct > modelRow.blendPct;

  return (
    <div>
      <div className="mb-5">
        <h2 className="section-heading mb-1">Model vs Naive Baselines</h2>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          The honest scoreboard: how the model compares against strategies that need no model at
          all. The best figure in each column is highlighted — even when a baseline wins it.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {["Strategy", "Winner Called", "Podium Set", "Points Set", "Blend", "Mean Error"].map(
                (h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider whitespace-nowrap"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {h}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.key}
                style={{
                  borderBottom: "1px solid var(--border)",
                  background: row.isModel ? "var(--bg-surface)" : "transparent",
                }}
              >
                <td className="px-4 py-3">
                  <p
                    className="font-bold flex items-center gap-2"
                    style={{ color: "var(--text)" }}
                  >
                    {row.isModel && (
                      <span
                        className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
                        style={{ background: "var(--accent-f1-red)" }}
                        aria-hidden
                      />
                    )}
                    {row.name}
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                    {row.description}
                  </p>
                </td>
                <td className="px-4 py-3 font-mono whitespace-nowrap">
                  <span style={cellStyle(row.winnerHitRate, best.winnerHitRate)}>
                    {row.winnerHits != null && row.roundsScored != null
                      ? `${row.winnerHits}/${row.roundsScored}`
                      : "–"}
                  </span>{" "}
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {row.winnerHitRate != null ? `(${row.winnerHitRate.toFixed(1)}%)` : ""}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono" style={cellStyle(row.podiumSetPct, best.podiumSetPct)}>
                  {fmtPct(row.podiumSetPct)}
                </td>
                <td className="px-4 py-3 font-mono" style={cellStyle(row.pointsSetPct, best.pointsSetPct)}>
                  {fmtPct(row.pointsSetPct)}
                </td>
                <td className="px-4 py-3 font-mono" style={cellStyle(row.blendPct, best.blendPct)}>
                  {fmtPct(row.blendPct)}
                </td>
                <td className="px-4 py-3 font-mono" style={cellStyle(row.meanError, best.meanError)}>
                  {row.meanError != null ? row.meanError.toFixed(2) : "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs mt-4 leading-relaxed" style={{ color: "var(--text-muted)" }}>
        Winner-only baselines (pole-sitter, points leader) predict just the race winner, so their
        podium, points, and error columns stay empty.{" "}
        {gridBeatsModelOnBlend ? (
          <>
            The qualifying grid remains a genuinely strong baseline — it currently edges the model
            on the podium-and-points blend, while the model leads on calling the actual race
            winner. We publish both so you can judge for yourself.
          </>
        ) : (
          <>We publish these comparisons every round so you can judge the model for yourself.</>
        )}
      </p>
    </div>
  );
}
