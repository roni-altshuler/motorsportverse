/**
 * BaselineLadder — the model and every yardstick it is measured against, ranked.
 *
 * **Baselines are never deleted** (docs/EVIDENCE.md rule 2). They stay live
 * even — especially — when the model beats them comfortably, because deleting
 * a baseline because it has been beaten is how a project loses the ability to
 * notice a regression.
 *
 * The ladder is ordered by the metric, not by which row is the model, so a
 * model that has fallen behind a trivial predictor **appears below it**. That
 * is the entire point: the reader sees the ordering, not a narrative about it.
 *
 * Rows carry the sample size because a mean over three rounds and a mean over
 * thirty are not the same claim, and a ladder that hides `n` invites the
 * reader to treat them alike.
 */
import * as React from "react";
import { cn } from "./cn";
import { count, num } from "./format";

export interface LadderRow {
  /** "This model", "Last race order", "Grid order", … */
  label: string;
  value: number | null;
  /** Rounds the value was averaged over. */
  n?: number | null;
  /** Exactly one row should set this — it gets the emphasis treatment. */
  isModel?: boolean;
  /** Optional one-line explanation, e.g. "predicts the previous finish". */
  hint?: string;
}

export function BaselineLadder({
  rows,
  metricLabel = "Mean position error",
  lowerIsBetter = true,
  className,
}: {
  rows: LadderRow[];
  metricLabel?: string;
  /** Position error and Brier are lower-is-better; hit rates are not. */
  lowerIsBetter?: boolean;
  className?: string;
}) {
  const scored = rows.filter((r) => r.value !== null && !Number.isNaN(r.value));
  // Unscored rows are kept and shown as absent rather than dropped: "we have
  // not measured this baseline yet" and "this baseline lost" are different
  // facts, and silently removing the first makes the ladder look complete.
  const unscored = rows.filter((r) => !scored.includes(r));

  const ordered = [...scored].sort((a, b) =>
    lowerIsBetter ? a.value! - b.value! : b.value! - a.value!,
  );
  const best = ordered[0]?.value ?? null;
  const worst = ordered[ordered.length - 1]?.value ?? null;
  const span = best !== null && worst !== null ? Math.abs(worst - best) : 0;

  const modelRank = ordered.findIndex((r) => r.isModel);
  const modelIsBeaten = modelRank > 0;

  return (
    <section
      data-testid="baseline-ladder"
      className={cn(
        "border border-[color:var(--hairline)] bg-[color:var(--surface-card)] p-5",
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="title-sm">Model vs baselines</h2>
        <span className="eyebrow">{metricLabel}</span>
      </div>

      <ol className="mt-4 space-y-2">
        {ordered.map((row, index) => {
          // Bar length is relative position within the observed span, so the
          // chart is readable when every forecaster lands within a point of
          // the others — an absolute scale would render five identical bars.
          const fraction =
            span > 0 && row.value !== null
              ? 1 - Math.abs(row.value - best!) / span
              : 1;
          return (
            <li key={row.label} className="flex items-center gap-3">
              <span className="font-mono font-tabular w-5 text-right text-[10px] text-[color:var(--muted)]">
                {index + 1}
              </span>
              <span
                className={cn(
                  "body-sm w-40 shrink-0 truncate",
                  row.isModel
                    ? "text-[color:var(--ink)]"
                    : "text-[color:var(--muted)]",
                )}
                title={row.hint ?? row.label}
              >
                {row.label}
              </span>
              <span className="h-1.5 flex-1 bg-[color:var(--surface-elevated)]">
                <span
                  className="block h-full"
                  style={{
                    width: `${Math.max(2, fraction * 100)}%`,
                    background: row.isModel
                      ? "var(--viz-model)"
                      : "var(--viz-baseline)",
                  }}
                />
              </span>
              {/* The number is always text beside the bar — a reader cannot
                  read 6.42 off a bar, and a colour-blind reader cannot read
                  "this one is the model" off a hue. */}
              <span className="font-mono font-tabular w-16 text-right text-xs text-[color:var(--ink)]">
                {num(row.value)}
              </span>
              <span className="font-mono font-tabular w-12 text-right text-[10px] text-[color:var(--muted)]">
                {row.n === null || row.n === undefined ? "" : `n=${count(row.n)}`}
              </span>
            </li>
          );
        })}
      </ol>

      {unscored.length ? (
        <ul className="mt-3 space-y-1">
          {unscored.map((row) => (
            <li key={row.label} className="text-[11px] text-[color:var(--muted)]">
              {row.label} — not yet measured
            </li>
          ))}
        </ul>
      ) : null}

      {modelIsBeaten ? (
        <p className="body-sm mt-4 text-[color:var(--warning)]">
          The model currently ranks {modelRank + 1} of {ordered.length}. A
          forecaster that cannot beat a trivial predictor does not serve, and
          this is stated rather than hidden.
        </p>
      ) : null}
    </section>
  );
}
