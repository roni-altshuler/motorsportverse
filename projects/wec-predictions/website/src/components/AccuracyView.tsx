"use client";

import { useState } from "react";

import ClassSelector from "@/components/ClassSelector";
import { EvidencePanel, type EvidenceBlock } from "@/components/ui/EvidencePanel";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Stat } from "@/components/ui/Stat";
import { pct } from "@/lib/format";
import type { CalibrationSummary, ClassMeta, SeasonAccuracyStat } from "@/types/wec";

export interface RoundAccuracyRow {
  round: number;
  name: string;
  n: number;
  mpe: number | null;
  podiumHits: number;
  exact: number;
  within3: number;
  winnerHit: boolean;
}

export interface ForwardEvalSummary {
  classRoundsScored: number;
  /** Model's combined win+podium probability error (lower is better). */
  model: number;
  baselines: { key: string; label: string; value: number; delta: number; notWorse: boolean }[];
}

const CLASS_FALLBACK: Record<string, string> = {
  HYPERCAR: "#3DDC97",
  LMP2: "#4EA8DE",
  LMGT3: "#F4A259",
};

function colorFor(key: string, classes: ClassMeta[]): string {
  return classes.find((c) => c.key === key)?.color ?? CLASS_FALLBACK[key] ?? "#999999";
}
function labelFor(key: string, classes: ClassMeta[]): string {
  return classes.find((c) => c.key === key)?.label ?? key;
}

/** Colour a mean-position-error cell — lower is better (green), higher warms. */
function mpeColor(mpe: number | null): string {
  if (mpe == null) return "var(--muted)";
  if (mpe <= 3.5) return "var(--success)";
  if (mpe <= 5.5) return "var(--warning)";
  return "var(--accent-negative)";
}

export default function AccuracyView({
  classes,
  overall,
  byClass,
  perRound,
  calibration,
  forwardEval,
  evidence,
}: {
  classes: ClassMeta[];
  overall: SeasonAccuracyStat;
  byClass: Record<string, SeasonAccuracyStat>;
  perRound: Record<string, RoundAccuracyRow[]>;
  calibration: CalibrationSummary | null;
  forwardEval: ForwardEvalSummary | null;
  evidence?: EvidenceBlock;
}) {
  // Classes that actually have per-round scored data drive the breakdown tabs.
  const scoredKeys = Object.keys(perRound);
  const selectorClasses: ClassMeta[] = scoredKeys.map((k) => ({
    key: k,
    label: labelFor(k, classes),
    color: colorFor(k, classes),
  }));
  const [activeClass, setActiveClass] = useState(selectorClasses[0]?.key ?? "");
  const rows = perRound[activeClass] ?? [];

  const byClassKeys = Object.keys(byClass);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <header className="mb-8">
        <p className="eyebrow mb-2">Track record</p>
        <h1 className="display-lg">Accuracy</h1>
        <p className="body-md mt-3 max-w-2xl text-[color:var(--muted)]">
          How the forecasts have actually scored against real results — measured across every scored
          class-round, with nothing left out. Endurance grids are large, so a car landing within a
          few places of its prediction is a strong result.
        </p>
      </header>

      <EvidencePanel evidence={evidence} className="mb-10" />

      {/* Overall KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-10">
        <Stat label="Class-rounds scored" value={overall.roundsScored} hint="predictions graded" />
        <Stat
          label="Mean position error"
          value={overall.meanPositionError != null ? overall.meanPositionError.toFixed(2) : "—"}
          hint="places off, on average"
        />
        <Stat label="Podium hit rate" value={pct(overall.podiumHitRate)} hint="predicted podium correct" />
        <Stat label="Winner hit rate" value={pct(overall.winnerHitRate)} hint="predicted winner correct" />
      </div>

      {/* Per-class accuracy */}
      <h2 className="section-heading text-[24px] mb-4">By class</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-12">
        {byClassKeys.map((key) => {
          const a = byClass[key];
          const color = colorFor(key, classes);
          return (
            <Card key={key} className="p-5" data-class={key}>
              <div className="flex items-center justify-between mb-4">
                <span className="class-chip" data-class={key} style={{ ["--class-color" as string]: color }}>
                  {labelFor(key, classes)}
                </span>
                <Badge variant="muted">{a.roundsScored}R</Badge>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <p className="eyebrow">Mean err.</p>
                  <p className="title-md font-tabular mt-1" style={{ color: mpeColor(a.meanPositionError) }}>
                    {a.meanPositionError != null ? a.meanPositionError.toFixed(2) : "—"}
                  </p>
                </div>
                <div>
                  <p className="eyebrow">Podium</p>
                  <p className="title-md font-tabular mt-1 text-[color:var(--ink)]">{pct(a.podiumHitRate)}</p>
                </div>
                <div>
                  <p className="eyebrow">Winner</p>
                  <p className="title-md font-tabular mt-1 text-[color:var(--ink)]">{pct(a.winnerHitRate)}</p>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Per-round breakdown */}
      {selectorClasses.length > 0 && (
        <>
          <div className="flex flex-wrap items-end justify-between gap-4 mb-4">
            <h2 className="section-heading text-[24px] !mb-0">Round by round</h2>
            <ClassSelector classes={selectorClasses} value={activeClass} onChange={setActiveClass} size="sm" />
          </div>
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse">
                <thead>
                  <tr>
                    {["Round", "Cars", "Mean error", "Podium", "Exact", "Within 3", "Winner"].map((h, i) => (
                      <th
                        key={i}
                        className="eyebrow px-4 py-3 border-b border-[color:var(--hairline)] whitespace-nowrap"
                        style={{ textAlign: i === 0 ? "left" : "right" }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.round} className="transition-colors hover:bg-[color:var(--surface-elevated)]/40">
                      <td className="px-4 py-3 border-b border-[color:var(--hairline)]">
                        <a href={`/round/${r.round}`} className="hover:opacity-80">
                          <span className="eyebrow mr-2">R{r.round}</span>
                          <span className="text-[13px] text-[color:var(--ink)]">{r.name}</span>
                        </a>
                      </td>
                      <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular text-[color:var(--muted)]">
                        {r.n}
                      </td>
                      <td
                        className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular"
                        style={{ color: mpeColor(r.mpe) }}
                      >
                        {r.mpe != null ? r.mpe.toFixed(2) : "—"}
                      </td>
                      <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular text-[color:var(--ink)]">
                        {r.podiumHits}/3
                      </td>
                      <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular text-[color:var(--muted)]">
                        {r.exact}/{r.n}
                      </td>
                      <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right font-tabular text-[color:var(--muted)]">
                        {r.within3}/{r.n}
                      </td>
                      <td className="px-4 py-3 border-b border-[color:var(--hairline)] text-right">
                        {r.winnerHit ? (
                          <span style={{ color: "var(--success)" }}>✓</span>
                        ) : (
                          <span className="text-[color:var(--muted-soft)]">✗</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      {/* Forecast vs baselines (only when forward evaluation is published) */}
      {forwardEval && forwardEval.baselines.length > 0 && (
        <div className="mt-12">
          <h2 className="section-heading text-[24px] mb-2">Does the forecast beat guesswork?</h2>
          <p className="body-sm text-[color:var(--muted)] max-w-2xl mb-5">
            Combined win + podium forecast error across {forwardEval.classRoundsScored} scored
            class-round{forwardEval.classRoundsScored === 1 ? "" : "s"} — lower is better — measured
            against two naive baselines: simply repeating the last race&rsquo;s order, and ranking cars
            by their season points.
          </p>
          <Card className="p-5 sm:p-6">
            <div className="flex flex-wrap items-baseline gap-3 mb-6">
              <span className="eyebrow">Model forecast error</span>
              <span className="display-md font-tabular" style={{ color: "var(--accent-f1-red-bright)" }}>
                {forwardEval.model.toFixed(3)}
              </span>
              <span className="body-sm text-[color:var(--muted)]">lower is better</span>
            </div>
            <div className="flex flex-col gap-3">
              {forwardEval.baselines.map((b) => {
                const beats = b.delta <= -0.002;
                const verdict = beats ? "Beats it" : b.notWorse ? "Matches it" : "Behind";
                const variant = beats ? "positive" : b.notWorse ? "info" : "negative";
                return (
                  <div
                    key={b.key}
                    className="flex items-center justify-between gap-4 py-3 border-b border-[color:var(--hairline)]"
                  >
                    <div className="min-w-0">
                      <p className="text-[13px] text-[color:var(--ink)] font-mono tracking-[0.02em]">{b.label}</p>
                      <p className="text-[11px] text-[color:var(--muted)]">baseline error {b.value.toFixed(3)}</p>
                    </div>
                    <div className="flex items-center gap-4">
                      <span
                        className="font-tabular text-[13px]"
                        style={{ color: b.delta <= 0 ? "var(--success)" : "var(--accent-negative)" }}
                      >
                        {b.delta <= 0 ? "−" : "+"}
                        {Math.abs(b.delta).toFixed(3)}
                      </span>
                      <Badge variant={variant}>{verdict}</Badge>
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="mt-5 text-[11px] text-[color:var(--muted-soft)]">
              &ldquo;Matches it&rdquo; means the model is statistically no worse than that baseline over
              the rounds scored so far. On a young season with few rounds, matching a strong
              season-form baseline while beating last-race form is an honest, expected result.
            </p>
          </Card>
        </div>
      )}

      {/* Model notes */}
      <div className="mt-12 grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-5">
          <h3 className="title-sm mb-2">Calibration</h3>
          {calibration?.applied ? (
            <p className="body-sm text-[color:var(--muted)]">
              Probabilities are calibrated on {calibration.trainingRounds} real round
              {calibration.trainingRounds === 1 ? "" : "s"} of results, per class. {calibration.dataLimitation}
            </p>
          ) : (
            <p className="body-sm text-[color:var(--muted)]">
              Calibration is held back until enough real rounds have accrued — the forecasts are not
              claimed to be calibrated on synthetic data.
            </p>
          )}
        </Card>
        <Card className="p-5">
          <h3 className="title-sm mb-2">Continuous evaluation</h3>
          <p className="body-sm text-[color:var(--muted)]">
            {forwardEval
              ? "Every round is re-scored against simple baselines as results come in, so the track record above updates honestly over the season — no cherry-picking, nothing dropped."
              : "A rolling forward-evaluation summary (forecast quality vs baselines, round over round) is not published for this season yet — the honest, per-round scores above are the current record."}
          </p>
        </Card>
      </div>
    </div>
  );
}
