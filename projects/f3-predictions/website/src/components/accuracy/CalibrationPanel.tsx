import type { CalibrationSummary } from "@/types/f3";

const MARKET_LABELS: Record<string, string> = {
  win: "Win",
  podium: "Podium",
  top6: "Top 6",
  top10: "Top 10",
};

const MARKET_ORDER = ["win", "podium", "top6", "top10"];

function marketLabel(key: string): string {
  return MARKET_LABELS[key] ?? key;
}

/**
 * Renders calibration_summary.json — the honest calibration status the F3 model
 * earned once real rounds were backfilled. Adapts the F1 flagship's calibration
 * panel to F3's shape: applied flag, training-round count, and the per-market
 * observation counts the isotonic calibrator was fitted on. (The values in
 * `perMarket` are sample counts, not temperatures — labelled as such.)
 */
export default function CalibrationPanel({
  summary,
}: {
  summary: CalibrationSummary | null;
}) {
  if (!summary) return null;

  const markets = MARKET_ORDER.filter((m) => m in summary.perMarket).concat(
    Object.keys(summary.perMarket).filter((m) => !MARKET_ORDER.includes(m)),
  );

  return (
    <section className="mt-12">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="eyebrow mb-1">Probability calibration</p>
          <h2 className="text-xl font-semibold text-[var(--ink)]">
            How trustworthy the probabilities are
          </h2>
        </div>
        <span
          className="rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider"
          style={{
            background: summary.applied
              ? "color-mix(in srgb, var(--accent) 16%, transparent)"
              : "var(--surface-2)",
            color: summary.applied ? "var(--accent)" : "var(--ink-muted)",
            border: `1px solid ${
              summary.applied
                ? "color-mix(in srgb, var(--accent) 40%, transparent)"
                : "var(--hairline)"
            }`,
          }}
        >
          {summary.applied ? "Calibration applied" : "Calibration pending"}
        </span>
      </div>

      <div className="rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-6">
        <p className="text-sm text-[var(--ink-muted)]">
          A well-calibrated model assigns probabilities that match how often things
          actually happen. F3&rsquo;s forecasts are tuned against the real classified
          results so a stated 30% podium chance means roughly 3-in-10 over the long run.
        </p>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="rounded-[var(--radius-md)] border border-[var(--hairline)] p-4">
            <p className="mono-label">Training rounds</p>
            <p className="font-display font-tabular mt-1 text-2xl font-bold text-[var(--ink)]">
              {summary.trainingRounds}
            </p>
            <p className="mt-1 text-xs text-[var(--ink-dim)]">real completed rounds</p>
          </div>
          <div className="rounded-[var(--radius-md)] border border-[var(--hairline)] p-4 sm:col-span-1 lg:col-span-2">
            <p className="mono-label">Status</p>
            <p className="mt-1 text-sm text-[var(--ink)]">{summary.dataLimitation}</p>
            {summary.generatedAt && (
              <p className="mt-2 text-xs text-[var(--ink-dim)]">
                Generated {new Date(summary.generatedAt).toLocaleString()}
              </p>
            )}
          </div>
        </div>

        <p className="mt-6 mb-3 mono-label">Calibration samples per market</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {markets.map((m) => (
            <div
              key={m}
              className="rounded-[var(--radius-md)] border border-[var(--hairline)] bg-[var(--surface-2)] p-4 text-center"
            >
              <p className="text-xs uppercase tracking-wider text-[var(--ink-muted)]">
                {marketLabel(m)}
              </p>
              <p className="font-display font-tabular mt-1 text-xl font-bold text-[var(--ink)]">
                {summary.perMarket[m].toLocaleString()}
              </p>
              <p className="mt-0.5 text-[10px] text-[var(--ink-dim)]">observations</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-[var(--ink-dim)]">
          Each figure is how many prior driver-outcomes fed the calibrator for that
          market. More samples means a steadier probability estimate.
        </p>
      </div>
    </section>
  );
}
