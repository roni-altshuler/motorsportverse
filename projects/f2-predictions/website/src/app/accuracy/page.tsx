import type { Metadata } from "next";

import CalibrationPanel from "@/components/accuracy/CalibrationPanel";
import CandidateModelCard from "@/components/accuracy/CandidateModelCard";
import HistoricalBacktestPanel from "@/components/accuracy/HistoricalBacktestPanel";
import RoundsHeatmap from "@/components/accuracy/RoundsHeatmap";
import WalkForwardPanel from "@/components/accuracy/WalkForwardPanel";
import { Sparkline } from "@/components/charts/Sparkline";
import ShareButton from "@/components/ShareButton";
import {
  getCalibrationSummary,
  getF2Data,
  getForwardEvalRounds,
  getForwardEvalSeason,
  getHistoricalBacktest,
  getModelHealth,
  getPromotionStatus,
} from "@/lib/f2data";
import { EvidencePanel } from "@/components/ui/EvidencePanel";
import { getEvidence } from "@/lib/evidence";

export const metadata: Metadata = { title: "Accuracy — RaceIQ F2" };

function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${(v * 100).toFixed(0)}%`;
}

function fmt(v: number | null | undefined, digits = 2): string {
  return v == null ? "—" : v.toFixed(digits);
}

export default function AccuracyPage() {
  const data = getF2Data();
  const season = getForwardEvalSeason();
  const rounds = getForwardEvalRounds();
  const health = getModelHealth();
  const calibration = getCalibrationSummary();
  const promotion = getPromotionStatus();
  const backtest = getHistoricalBacktest();

  const acc = data.seasonAccuracy;
  const brierSeries = (health?.brierByRound ?? []).map((b) => b.brier);

  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <EvidencePanel evidence={getEvidence()} className="mb-10" />
      <p className="eyebrow mb-3">Formula 2 · {data.season}</p>
      <h1 className="font-display text-4xl font-bold tracking-tight text-[var(--ink)] sm:text-5xl">
        Model accuracy
      </h1>
      <p className="mt-3 text-[var(--ink-muted)]">
        How the F2 model&rsquo;s evaluation forecasts have scored against the actual
        results, over {acc?.roundsScored ?? data.completedRounds} completed rounds of {data.season}.
      </p>

      <section aria-label="Scoring scope" className="mt-6 rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-5">
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="mono-label">Position metrics</dt>
            <dd className="mt-1 text-[var(--ink-muted)]">
              {season?.finishersOnly === false ? "Scope not recorded" : "Ranked finishers only"}
            </dd>
          </div>
          <div>
            <dt className="mono-label">Win / podium probabilities</dt>
            <dd className="mt-1 text-[var(--ink-muted)]">
              {season?.marketScope ?? (season?.finishersOnly ? "Finishers only (legacy artifact)" : "Scope not recorded")}
            </dd>
          </div>
        </dl>
        <p className="mt-4 border-t border-[var(--hairline)] pt-4 text-sm text-[var(--ink-muted)]">
          {season?.basis === "walk_forward_replay"
            ? "Retrospective walk-forward replay, using prior-round data. This is not an immutable record of forecasts published before each race."
            : "Evaluation basis and publication timing are not recorded in this artifact."}
        </p>
      </section>

      <div className="mt-6">
        <ShareButton
          title={`RaceIQ F2 — ${data.season} model accuracy`}
          text={`How the RaceIQ F2 model has scored against real ${data.season} FIA Formula 2 results.`}
        />
      </div>

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

      {/* Per-round table with probability quality */}
      {rounds.length > 0 && (
        <section className="mt-12">
          <h2 className="mb-4 text-xl font-semibold text-[var(--ink)]">Per round (feature race)</h2>
          <div role="region" aria-label="Feature race score table" tabIndex={0} className="overflow-x-auto rounded-[var(--radius-lg)] border border-[var(--hairline)] focus-visible:outline-2 focus-visible:outline-[var(--accent)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[var(--surface-2)] text-left text-xs uppercase tracking-wider text-[var(--ink-dim)]">
                  <th className="px-4 py-3 font-medium">Round</th>
                  <th className="px-4 py-3 font-medium">Winner</th>
                  <th className="px-4 py-3 font-medium">Podium hits</th>
                  <th className="px-4 py-3 font-medium">Mean error</th>
                  <th className="hidden px-4 py-3 font-medium sm:table-cell">NDCG@5</th>
                  <th className="px-4 py-3 font-medium">Win Brier</th>
                </tr>
              </thead>
              <tbody>
                {rounds.map((r) => {
                  const winScore = r.markets?.feature?.win;
                  return (
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
                        {r.feature.mean_position_error ?? "-"}
                        <span className="block whitespace-nowrap text-xs text-[var(--ink-dim)]">n={r.feature.n} ranked</span>
                      </td>
                      <td className="hidden px-4 py-3 tabular-nums text-[var(--ink-muted)] sm:table-cell">
                        {r.feature.ndcg_at_5 != null ? r.feature.ndcg_at_5.toFixed(2) : "—"}
                      </td>
                      <td className="px-4 py-3 tabular-nums text-[var(--ink-muted)]">
                        {fmt(winScore?.brier, 4)}
                        {winScore && (
                          <span className="block whitespace-nowrap text-xs text-[var(--ink-dim)]">
                            {winScore.n != null ? `n=${winScore.n} entrants` : winScore.brier != null ? "Sample count not recorded" : "Not scored"}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-[var(--ink-dim)]">
            Win Brier scores the model&rsquo;s win probabilities against who actually won - lower is
            sharper and better calibrated.
          </p>
          <p className="mt-1 text-xs text-[var(--ink-muted)] sm:hidden">
            Scroll the table horizontally to see probability scores.
          </p>
        </section>
      )}

      {/* Walk-forward: model vs the trivial last-race baseline */}
      <WalkForwardPanel season={season} />

      {/* Candidate model A/B status */}
      <CandidateModelCard status={promotion} />

      {/* Calibration status */}
      <CalibrationPanel summary={calibration} />

      {/* Historical backtest dashboard */}
      {backtest && backtest.roundsEvaluated > 0 && <HistoricalBacktestPanel data={backtest} />}

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
                    <li key={a} style={{ color: "var(--warning)" }}>
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
                Feature drift and rolling-Brier are tracked round-to-round; a spike flags where the
                field behaved unlike the rounds the model learned from.
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
