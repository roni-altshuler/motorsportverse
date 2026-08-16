/**
 * EvidencePanel — the model against the baseline it has to beat.
 *
 * **Deliberately not a tab.** Every probability on these sites is unfalsifiable
 * without it, and a tab is a place things go to be unread. It renders below the
 * numbers it justifies, on every page that shows a forecast, and there is a
 * test asserting it is present.
 *
 * It leads with the gap to a *baseline* rather than with an accuracy, because
 * an accuracy with no benchmark is a number about the calendar — a season of
 * processional races flatters any model, and a wet one buries it. And it labels
 * the basis: a forward evaluation is not a backtest, and the two are never
 * merged.
 *
 * The comparison is computed once in Python (`motorsport_core.evidence`) and
 * published as `evidence.json`. This component renders it and does not
 * recompute — a component that recomputes is a second model nobody benchmarked.
 *
 * Series-agnostic by construction: it styles through CSS custom properties and
 * reads a shape every series publishes, so one source renders under all six
 * accents.
 */
import * as React from "react";
import { cn } from "./cn";
import { ABSENT, count, num, stamp } from "./format";

export interface EvidenceComparison {
  metric: string;
  baseline: string;
  baselineLabel: string;
  raceType: string;
  lowerIsBetter: boolean;
  nRounds: number;
  modelMean: number | null;
  baselineMean: number | null;
  improvement: number | null;
  ciLow: number | null;
  ciHigh: number | null;
  verdict: "better" | "worse" | "inconclusive" | "insufficient" | string;
  note: string;
}

export interface EvidenceBlock {
  available: boolean;
  reason?: string | null;
  season?: number | null;
  generatedAt?: string | null;
  roundsScored?: number;
  basis?: string;
  headline?: EvidenceComparison | null;
  comparisons?: EvidenceComparison[];
  calibration?: {
    applied: boolean;
    trainingRounds?: number | null;
    note?: string;
  } | null;
  caveats?: string[];
}

const VERDICT_COPY: Record<string, string> = {
  better: "beats the baseline",
  worse: "does NOT beat the baseline",
  inconclusive: "no difference demonstrated",
  insufficient: "too few rounds to say",
};

/**
 * Verdict colour. Note that `worse` is NOT rendered in the negative accent:
 * the site accent means "this series", and a measured shortfall is information
 * rather than an error state. `warning` is the backtest-and-caveat colour and
 * carries the right weight — noticeable, not alarming.
 */
function verdictTone(verdict: string): string {
  switch (verdict) {
    case "better":
      return "text-[color:var(--success)]";
    case "worse":
      return "text-[color:var(--warning)]";
    default:
      return "text-[color:var(--muted)]";
  }
}

export function EvidencePanel({
  evidence,
  className,
  title = "Evidence",
}: {
  evidence: EvidenceBlock | null | undefined;
  className?: string;
  title?: string;
}) {
  // No benchmark is a state worth rendering. A forecast page with a silently
  // absent evidence panel reads as a page with nothing to hide.
  if (!evidence?.available) {
    return (
      <section
        data-testid="evidence-panel"
        className={cn(
          "border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-5",
          className,
        )}
      >
        <h2 className="title-sm">{title}</h2>
        <p className="body-sm mt-2 text-[color:var(--muted)]">
          No benchmark has been published yet
          {evidence?.reason ? ` — ${evidence.reason}` : ""}. Until one is, treat
          every probability on this page as unverified.
        </p>
      </section>
    );
  }

  const rows = (evidence.comparisons ?? []).filter(
    (c) => c.metric === "mean_position_error",
  );
  const headline = evidence.headline ?? rows[0] ?? null;

  return (
    <section
      data-testid="evidence-panel"
      className={cn(
        "border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-5",
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="title-sm">{title}</h2>
        <span className="font-mono text-[10px] text-[color:var(--muted)]">
          {stamp(evidence.generatedAt)}
        </span>
      </div>

      {headline ? (
        <p className="body-sm mt-3 text-[color:var(--body)]">
          Over{" "}
          <span className="font-tabular">{count(headline.nRounds)}</span> paired
          round{headline.nRounds === 1 ? "" : "s"}, the model{" "}
          <span className={verdictTone(headline.verdict)}>
            {VERDICT_COPY[headline.verdict] ?? headline.verdict}
          </span>{" "}
          ({headline.baselineLabel.toLowerCase()}).
        </p>
      ) : null}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-[color:var(--hairline)]">
              <th scope="col" className="eyebrow py-2 pr-3">Baseline</th>
              <th scope="col" className="eyebrow py-2 pr-3">Race</th>
              <th scope="col" className="eyebrow py-2 pr-3 text-right">Rounds</th>
              <th scope="col" className="eyebrow py-2 pr-3 text-right">Model</th>
              <th scope="col" className="eyebrow py-2 pr-3 text-right">Baseline</th>
              <th scope="col" className="eyebrow py-2 pr-3 text-right">Gain</th>
              <th scope="col" className="eyebrow py-2">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={`${row.baseline}-${row.raceType}-${row.metric}`}
                className="border-b border-[color:var(--hairline)] last:border-0"
              >
                <td className="body-sm py-2 pr-3">{row.baselineLabel}</td>
                <td className="body-sm py-2 pr-3 capitalize">{row.raceType}</td>
                <td className="font-mono font-tabular py-2 pr-3 text-right text-xs">
                  {count(row.nRounds)}
                </td>
                <td className="font-mono font-tabular py-2 pr-3 text-right text-xs">
                  {num(row.modelMean)}
                </td>
                <td className="font-mono font-tabular py-2 pr-3 text-right text-xs">
                  {num(row.baselineMean)}
                </td>
                <td className="font-mono font-tabular py-2 pr-3 text-right text-xs">
                  {/* Signed on purpose: a negative gain is the whole point of
                      publishing this column at all. */}
                  {row.improvement === null
                    ? ABSENT
                    : `${row.improvement >= 0 ? "+" : ""}${num(row.improvement)}`}
                </td>
                <td className={cn("body-sm py-2", verdictTone(row.verdict))}>
                  {VERDICT_COPY[row.verdict] ?? row.verdict}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {headline && headline.ciLow !== null && headline.ciHigh !== null ? (
        <p className="mt-4 text-[11px] leading-relaxed text-[color:var(--muted)]">
          Paired bootstrap on the round-by-round difference: {num(headline.improvement, 3)},
          95% CI [{num(headline.ciLow, 3)}, {num(headline.ciHigh, 3)}] in positions
          gained. Positive means the model is closer to the real finishing order
          than {headline.baselineLabel.toLowerCase()} is
          {headline.ciLow > 0
            ? "; the whole interval is above zero"
            : headline.ciHigh < 0
              ? "; the whole interval is BELOW zero, so the shortfall is measured, not noise"
              : "; the interval covers zero, so no difference has been demonstrated"}
          .
        </p>
      ) : null}

      <p className="mt-3 text-[11px] leading-relaxed text-[color:var(--muted)]">
        {evidence.basis}. Historical replays and the forward record are computed
        separately and never merged.
      </p>

      {evidence.caveats?.length ? (
        <ul className="mt-3 space-y-1">
          {evidence.caveats.map((caveat) => (
            <li
              key={caveat}
              className="text-[11px] leading-relaxed text-[color:var(--muted)]"
            >
              {caveat}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
