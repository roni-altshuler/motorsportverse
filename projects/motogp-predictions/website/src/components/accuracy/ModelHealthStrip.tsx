/**
 * ModelHealthStrip — a small, honest "is the model still healthy?" strip.
 *
 * Reads `model_health.json` (MotoGP's camelCase `ModelHealth`). It separates the two
 * things that are easy to conflate: whether the FORECASTS are still landing well
 * (output quality, the rolling probability-error trend) versus whether the
 * model's INPUTS have drifted from what it was tuned on. Input drift is watched
 * but does not, on its own, mean the predictions have degraded — so the headline
 * status follows output quality and input shifts are shown as a separate signal.
 *
 * Ported from the RaceIQ F1 flagship's ModelHealthPanel. Every field is optional;
 * the strip renders only what the file provides and hides entirely when the file
 * is missing. This is a compact top-of-page summary — the detailed Brier trend +
 * diagnostics section still lives lower on the accuracy page.
 */
import type { ModelHealth } from "@/types/motogp";

const FEATURE_LABELS: Record<string, string> = {
  predictedValue: "Predicted pace",
  pWin: "Win probability",
  pPodium: "Podium probability",
  meanFinish: "Mean finish",
  finishRangeLow: "Finish range (low)",
  finishRangeHigh: "Finish range (high)",
};

function prettifyFeature(feature: string): string {
  if (FEATURE_LABELS[feature]) return FEATURE_LABELS[feature];
  return feature
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/^./, (c) => c.toUpperCase());
}

type Tone = "good" | "warn" | "bad" | "neutral";

function severityTone(severity: string | undefined): Tone {
  switch ((severity ?? "").toLowerCase()) {
    case "ok":
    case "none":
    case "stable":
      return "good";
    case "warn":
    case "warning":
      return "warn";
    case "alarm":
    case "critical":
      return "bad";
    default:
      return "neutral";
  }
}

const TONE_DOT: Record<Tone, string> = {
  good: "var(--success)",
  warn: "var(--warning)",
  bad: "var(--accent)",
  neutral: "var(--ink-dim)",
};

const TONE_PILL: Record<Tone, { background: string; color: string }> = {
  good: { background: "rgba(95,166,87,0.14)", color: "var(--success)" },
  warn: { background: "rgba(212,160,23,0.14)", color: "var(--warning)" },
  bad: { background: "color-mix(in srgb, var(--accent) 14%, transparent)", color: "var(--accent)" },
  neutral: { background: "rgba(136,136,136,0.12)", color: "var(--ink-dim)" },
};

const SEVERITY_LABEL: Record<Tone, string> = {
  good: "Stable",
  warn: "Shifting",
  bad: "Shifted",
  neutral: "Unknown",
};

export default function ModelHealthStrip({ health }: { health: ModelHealth | null }) {
  if (!health) return null;

  const output = health.outputDrift;
  const drift = (health.featureDrift ?? []).slice();
  const trend = (health.brierByRound ?? []).filter((d) => typeof d.brier === "number");

  // Nothing meaningful to show — bail rather than render an empty shell.
  if (!output && drift.length === 0 && trend.length === 0) return null;

  // Headline status follows OUTPUT quality (are the forecasts still good?).
  const outTone = output ? severityTone(output.severity) : "neutral";
  const statusLabel =
    outTone === "good"
      ? "Healthy"
      : outTone === "warn"
        ? "Watch"
        : outTone === "bad"
          ? "Degraded"
          : "Monitoring";

  // relativeChange is (recent − baseline) / baseline on the error metric, so a
  // negative value means the recent error is LOWER than the baseline — better.
  const rel = output?.relativeChange ?? null;
  const relPct = rel != null ? Math.abs(rel) * 100 : null;
  const relBetter = rel != null ? rel < 0 : null;

  const shiftedCount = drift.filter((d) => severityTone(d.severity) !== "good").length;
  const roundsMonitored = output?.roundsCompared ?? trend.length;

  return (
    <section className="mt-12">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold text-[var(--ink)]">Model health at a glance</h2>
        <span
          className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold uppercase tracking-wider"
          style={TONE_PILL[outTone]}
        >
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: TONE_DOT[outTone] }}
            aria-hidden
          />
          {statusLabel}
        </span>
      </div>
      <p className="mb-5 max-w-2xl text-sm text-[var(--ink-muted)]">
        A self-check on the live model: whether recent forecasts are still landing as well as they
        should, and whether the numbers feeding the model have drifted from what it was tuned on.
      </p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-[var(--radius-md)] border border-[var(--hairline)] bg-[var(--surface)] p-4">
          <p className="mono-label mb-2">Forecast quality</p>
          {relPct != null ? (
            <>
              <p
                className="font-tabular text-2xl font-bold tracking-tight"
                style={{ color: relBetter ? "var(--success)" : "var(--accent)" }}
              >
                {relBetter ? "▼" : "▲"} {relPct.toFixed(0)}%
              </p>
              <p className="mt-1 text-[11px] text-[var(--ink-dim)]">
                {relBetter ? "lower error than" : "higher error than"} the season benchmark
              </p>
            </>
          ) : (
            <p className="text-sm text-[var(--ink-muted)]">Not enough graded rounds yet.</p>
          )}
        </div>
        <div className="rounded-[var(--radius-md)] border border-[var(--hairline)] bg-[var(--surface)] p-4">
          <p className="mono-label mb-2">Rounds monitored</p>
          <p className="font-tabular text-2xl font-bold tracking-tight text-[var(--ink)]">
            {roundsMonitored || "—"}
          </p>
          <p className="mt-1 text-[11px] text-[var(--ink-dim)]">recent rounds in the rolling check</p>
        </div>
        <div className="rounded-[var(--radius-md)] border border-[var(--hairline)] bg-[var(--surface)] p-4">
          <p className="mono-label mb-2">Input drift</p>
          <p
            className="font-tabular text-2xl font-bold tracking-tight"
            style={{ color: shiftedCount > 0 ? "var(--warning)" : "var(--success)" }}
          >
            {drift.length > 0 ? `${shiftedCount}/${drift.length}` : "—"}
          </p>
          <p className="mt-1 text-[11px] text-[var(--ink-dim)]">model inputs that moved vs baseline</p>
        </div>
      </div>

      {drift.length > 0 && (
        <div className="mt-5">
          <p className="mono-label mb-2">Input drift by feature</p>
          <div className="flex flex-wrap gap-2">
            {drift.map((d) => {
              const tone = severityTone(d.severity);
              return (
                <span
                  key={d.feature}
                  className="inline-flex items-center gap-1.5 rounded-full border border-[var(--hairline)] bg-[var(--surface)] px-2.5 py-1 text-xs"
                >
                  <span
                    className="inline-block h-1.5 w-1.5 rounded-full"
                    style={{ background: TONE_DOT[tone] }}
                    aria-hidden
                  />
                  <span className="text-[var(--ink)]">{prettifyFeature(d.feature)}</span>
                  <span className="text-[var(--ink-dim)]">· {SEVERITY_LABEL[tone]}</span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      {shiftedCount > 0 && (
        <p className="mt-4 text-xs leading-relaxed text-[var(--ink-dim)]">
          Some model inputs have drifted from their reference range — normal early in a season with a
          small sample of rounds so far. It is flagged here for transparency, but the rolling
          forecast-quality check shows the predictions themselves are{" "}
          {outTone === "good" ? "still holding up" : "being watched closely"}.
        </p>
      )}
    </section>
  );
}
