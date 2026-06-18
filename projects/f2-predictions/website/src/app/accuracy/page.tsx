import type { Metadata } from "next";

import RoundsHeatmap from "@/components/accuracy/RoundsHeatmap";
import { Sparkline } from "@/components/charts/Sparkline";
import {
  getCalibrationSummary,
  getF2Data,
  getForwardEvalRounds,
  getForwardEvalSeason,
  getModelHealth,
} from "@/lib/f2data";

export const metadata: Metadata = { title: "Accuracy — RaceIQ F2" };

function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${(v * 100).toFixed(0)}%`;
}

export default function AccuracyPage() {
  const data = getF2Data();
  const season = getForwardEvalSeason();
  const rounds = getForwardEvalRounds();
  const health = getModelHealth();
  const calibration = getCalibrationSummary();

  const acc = data.seasonAccuracy;
  const brierSeries = (health?.brierByRound ?? []).map((b) => b.brier);

  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <p className="eyebrow mb-3">Formula 2 · {data.season}</p>
      <h1 className="font-display text-4xl font-bold tracking-tight text-[var(--ink)] sm:text-5xl">
        Model accuracy
      </h1>
      <p className="mt-3 text-[var(--ink-muted)]">
        How the F2 model&rsquo;s leakage-safe pre-race forecasts have scored against the actual
        results, over {acc?.roundsScored ?? data.completedRounds} completed rounds of {data.season}.
      </p>

      {/* Honest calibration banner — mirrors F1's gate. */}
      {calibration && !calibration.applied && (
        <div className="mt-8 rounded-[var(--radius-md)] border border-[color-mix(in_srgb,var(--accent)_40%,transparent)] bg-[color-mix(in_srgb,var(--accent)_8%,transparent)] px-4 py-3 text-sm text-[var(--ink-muted)]">
          <span className="font-semibold text-[var(--ink)]">Calibration pending.</span>{" "}
          {calibration.dataLimitation}
        </div>
      )}

      {/* Headline metrics */}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Winner hit rate" value={pct(acc?.winnerHitRate ?? season?.winnerHitRate)} />
        <Metric label="Podium hit rate" value={pct(acc?.podiumHitRate ?? season?.podiumHitRate)} />
        <Metric
          label="Mean position error"
          value={acc?.meanPositionError != null ? acc.meanPositionError.toFixed(2) : "—"}
        />
        <Metric label="NDCG@5" value={season?.meanNdcgAt5 != null ? season.meanNdcgAt5.toFixed(2) : "—"} />
      </div>

      {/* Per-round accuracy heatmap */}
      {rounds.length > 0 && (
        <section className="mt-12">
          <h2 className="mb-4 text-xl font-semibold text-[var(--ink)]">Per-round accuracy</h2>
          <p className="mb-4 text-sm text-[var(--ink-muted)]">
            Podium-weighted feature-race accuracy per round. Tap a cell for the breakdown.
          </p>
          <RoundsHeatmap rounds={rounds} totalRounds={data.totalRounds} />
        </section>
      )}

      {/* Per-round table */}
      {rounds.length > 0 && (
        <section className="mt-12">
          <h2 className="mb-4 text-xl font-semibold text-[var(--ink)]">Per round (feature race)</h2>
          <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--hairline)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[var(--surface-2)] text-left text-xs uppercase tracking-wider text-[var(--ink-dim)]">
                  <th className="px-4 py-3 font-medium">Round</th>
                  <th className="px-4 py-3 font-medium">Winner</th>
                  <th className="px-4 py-3 font-medium">Podium hits</th>
                  <th className="px-4 py-3 font-medium">Mean error</th>
                  <th className="hidden px-4 py-3 font-medium sm:table-cell">NDCG@5</th>
                </tr>
              </thead>
              <tbody>
                {rounds.map((r) => (
                  <tr key={r.round} className="border-t border-[var(--hairline)] bg-[var(--surface)]">
                    <td className="px-4 py-3 text-[var(--ink)]">
                      R{r.round} · {r.venueName}
                    </td>
                    <td className="px-4 py-3">
                      <span style={{ color: r.feature.winner_hit ? "var(--accent)" : "var(--ink-dim)" }}>
                        {r.feature.winner_hit ? "✓ hit" : "miss"}
                      </span>
                    </td>
                    <td className="px-4 py-3 tabular-nums text-[var(--ink-muted)]">
                      {r.feature.podium_hits ?? 0}/3
                    </td>
                    <td className="px-4 py-3 tabular-nums text-[var(--ink-muted)]">
                      {r.feature.mean_position_error ?? "—"}
                    </td>
                    <td className="hidden px-4 py-3 tabular-nums text-[var(--ink-muted)] sm:table-cell">
                      {r.feature.ndcg_at_5 != null ? r.feature.ndcg_at_5.toFixed(2) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Model health */}
      {health && (
        <section className="mt-12">
          <h2 className="mb-4 text-xl font-semibold text-[var(--ink)]">Model health</h2>
          <div className="grid gap-6 rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-6 lg:grid-cols-2">
            <div>
              <p className="eyebrow mb-2">Win-market Brier trend</p>
              <Sparkline points={brierSeries} />
              <p className="mt-2 text-xs text-[var(--ink-dim)]">
                Lower is better · {health.brierByRound.length} rounds
              </p>
            </div>
            <div>
              <p className="eyebrow mb-2">Diagnostics</p>
              {health.alarms.length === 0 && health.warnings.length === 0 ? (
                <p className="text-sm text-[var(--ink-muted)]">No drift warnings.</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {health.alarms.map((a) => (
                    <li key={a} style={{ color: "var(--maturity-experimental)" }}>
                      ⚠ {a}
                    </li>
                  ))}
                  {health.warnings.map((w) => (
                    <li key={w} className="text-[var(--ink-muted)]">
                      • {w}
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-3 text-xs text-[var(--ink-dim)]">
                Phase 1 runs on a synthetic source while the model warms up, so early-season
                distribution shift is expected.
              </p>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--hairline)] bg-[var(--surface)] p-4">
      <p className="mono-label">{label}</p>
      <p className="font-display font-tabular mt-1 text-2xl font-bold text-[var(--ink)]">{value}</p>
    </div>
  );
}
