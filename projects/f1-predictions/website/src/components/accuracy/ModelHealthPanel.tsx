"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";

import type { ModelHealthData } from "@/lib/data";

/**
 * ModelHealthPanel — a small, honest "is the model still healthy?" strip.
 *
 * Reads `model_health.json`. It separates the two things that are easy to
 * conflate: whether the FORECASTS are still landing well (output quality, the
 * rolling position-RMSE trend) versus whether the model's INPUTS
 * have drifted from what it was tuned on. Forecast drift is watched but does not,
 * on its own, mean the predictions have degraded — so the headline status
 * follows output quality and input shifts are shown as a separate signal.
 *
 * Every field is optional; the panel renders only what the file provides and
 * hides entirely when the file is missing.
 */

const FEATURE_LABELS: Record<string, string> = {
  predictedTime: "Predicted pace",
  winProbability: "Win probability",
  finishRangeLow: "Finish range (low)",
  finishRangeHigh: "Finish range (high)",
};

function prettifyFeature(feature: string): string {
  if (FEATURE_LABELS[feature]) return FEATURE_LABELS[feature];
  return feature.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, (c) => c.toUpperCase());
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
    case "notice":
      return "warn";
    case "alarm":
    case "critical":
    case "high":
      return "bad";
    default:
      return "neutral";
  }
}

const TONE_DOT: Record<Tone, string> = {
  good: "var(--success)",
  warn: "var(--warning)",
  bad: "#E10600",
  neutral: "var(--text-muted)",
};

const TONE_PILL: Record<Tone, { background: string; color: string }> = {
  good: { background: "rgba(95,166,87,0.14)", color: "var(--success)" },
  warn: { background: "rgba(212,160,23,0.14)", color: "var(--warning)" },
  bad: { background: "rgba(225,6,0,0.12)", color: "#E10600" },
  neutral: { background: "rgba(136,136,136,0.12)", color: "var(--text-muted)" },
};

const SEVERITY_LABEL: Record<Tone, string> = {
  good: "Stable",
  warn: "Shifting",
  bad: "Shifted",
  neutral: "Unknown",
};

export default function ModelHealthPanel({ health }: { health: ModelHealthData | null }) {
  if (!health) return null;

  if (health.diagnosticStatus !== "available" || health.outputMetric !== "rmse_position_error") {
    return (
      <section aria-label="Model health">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
          <h2 className="section-heading mb-0">Model Health</h2>
          <span
            className="text-xs font-bold uppercase tracking-wider"
            style={{ color: "var(--text-muted)" }}
          >
            Unavailable
          </span>
        </div>
        <p className="text-sm max-w-2xl" style={{ color: "var(--text-muted)" }}>
          {health.unavailableReason ?? "Eligible settled forecast diagnostics are unavailable."}
          {health.lastObservedRound != null
            ? ` Latest elapsed round: R${health.lastObservedRound}.`
            : ""}
        </p>
      </section>
    );
  }

  const output = health.outputDrift;
  const drift = (health.featureDrift ?? []).slice();
  const trend = (health.rmseByRound ?? []).filter((d) => Number.isFinite(d.rmse) && d.rmse >= 0);

  // Nothing meaningful to show — bail rather than render an empty shell.
  if (!output && drift.length === 0 && trend.length === 0) return null;

  // Headline status follows OUTPUT quality (are the forecasts still good?).
  const outTone = output?.relative_change != null ? severityTone(output.severity) : "neutral";
  const statusLabel =
    outTone === "good"
      ? "Stable error trend"
      : outTone === "warn"
        ? "Error increasing"
        : outTone === "bad"
          ? "Error increased"
          : output?.severity === "insufficient_baseline"
            ? "Comparison unavailable"
            : "Insufficient history";

  // relative_change is (recent − baseline) / baseline on the error metric, so a
  // negative value means the recent error is LOWER than the baseline — better.
  const rel = output?.relative_change ?? null;
  const relPct = rel != null ? Math.abs(rel) * 100 : null;
  const relBetter = rel != null ? rel < 0 : null;

  const shiftedCount = drift.filter((d) => severityTone(d.severity) !== "good").length;
  const chartData = trend.map((d) => ({ round: `R${d.round}`, err: d.rmse }));

  return (
    <section aria-label="Model health">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
        <h2 className="section-heading mb-0">Model Health</h2>
        <span
          className="text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-full inline-flex items-center gap-1.5"
          style={TONE_PILL[outTone]}
        >
          <span
            className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ background: TONE_DOT[outTone] }}
            aria-hidden
          />
          {statusLabel}
        </span>
      </div>
      <p className="text-sm mb-5 max-w-2xl" style={{ color: "var(--text-muted)" }}>
        Position error and forecast-distribution shifts across eligible settled rounds.
        {health.lastEvaluatedRound != null
          ? ` Evaluated through R${health.lastEvaluatedRound}.`
          : ""}
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
        <div className="metric-card">
          <p className="eyebrow mb-2">Error trend</p>
          {relPct != null ? (
            <>
              <p
                className="text-2xl font-mono font-bold tracking-tight"
                style={{
                  color: rel === 0 ? "var(--text)" : relBetter ? "var(--success)" : "#E10600",
                }}
              >
                {rel === 0 ? "–" : relBetter ? "▼" : "▲"} {relPct.toFixed(0)}%
              </p>
              <p className="text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
                {rel === 0 ? "same error as" : relBetter ? "lower error than" : "higher error than"}{" "}
                the previous rolling window
              </p>
            </>
          ) : (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              {output?.severity === "insufficient_baseline"
                ? "Relative change is unavailable because the prior window has zero error."
                : "Not enough graded rounds yet."}
            </p>
          )}
        </div>
        <div className="metric-card">
          <p className="eyebrow mb-2">Rounds monitored</p>
          <p
            className="text-2xl font-mono font-bold tracking-tight"
            style={{ color: "var(--text)" }}
          >
            {output?.rounds_compared ?? trend.length ?? "–"}
          </p>
          <p className="text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
            recent rounds in the rolling check
          </p>
        </div>
        <div className="metric-card">
          <p className="eyebrow mb-2">Forecast drift</p>
          <p
            className="text-2xl font-mono font-bold tracking-tight"
            style={{ color: shiftedCount > 0 ? "var(--warning)" : "var(--success)" }}
          >
            {drift.length > 0 ? `${shiftedCount}/${drift.length}` : "–"}
          </p>
          <p className="text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
            forecast features that moved vs earlier rounds
          </p>
        </div>
      </div>

      {drift.length > 0 && (
        <div className="mb-6">
          <p className="eyebrow mb-2">Forecast drift by feature</p>
          <div className="flex flex-wrap gap-2">
            {drift.map((d) => {
              const tone = severityTone(d.severity);
              return (
                <span
                  key={d.feature}
                  className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full"
                  style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
                >
                  <span
                    className="inline-block w-1.5 h-1.5 rounded-full"
                    style={{ background: TONE_DOT[tone] }}
                    aria-hidden
                  />
                  <span style={{ color: "var(--text)" }}>{prettifyFeature(d.feature)}</span>
                  <span style={{ color: "var(--text-muted)" }}>· {SEVERITY_LABEL[tone]}</span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      {chartData.length > 1 && (
        <div className="mb-4">
          <div className="mb-3">
            <h3
              className="font-bold text-sm uppercase tracking-wider"
              style={{ color: "var(--text)" }}
            >
              Position RMSE, Round by Round
            </h3>
            <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
              Root mean squared finishing-position error, in positions. Lower is better.
            </p>
          </div>
          <div className="w-full h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="round"
                  stroke="var(--text-muted)"
                  fontSize={12}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  stroke="var(--text-muted)"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  domain={[0, "auto"]}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--surface-card)",
                    border: "1px solid var(--hairline)",
                    borderRadius: 0,
                    color: "var(--ink)",
                    fontSize: "13px",
                    fontFamily: "var(--font-mono)",
                  }}
                  labelStyle={{
                    color: "var(--muted)",
                    letterSpacing: "1px",
                    textTransform: "uppercase",
                  }}
                  formatter={(value) => {
                    if (value == null) return [null, null];
                    return [Number(value).toFixed(2), "Position RMSE"];
                  }}
                />
                {output?.rolling_rmse_baseline != null && (
                  <ReferenceLine
                    y={output.rolling_rmse_baseline}
                    stroke="var(--text-muted)"
                    strokeDasharray="5 5"
                    strokeOpacity={0.7}
                    label={{
                      value: "prior window",
                      position: "right",
                      fill: "var(--text-muted)",
                      fontSize: 9,
                      fontFamily: "var(--font-mono)",
                      letterSpacing: "0.12em",
                    }}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="err"
                  stroke="var(--accent-f1-red)"
                  strokeWidth={2.5}
                  dot={{ fill: "var(--accent-f1-red)", r: 3 }}
                  activeDot={{ r: 5, strokeWidth: 0 }}
                  connectNulls
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {shiftedCount > 0 && (
        <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
          These forecast distributions differ from earlier eligible rounds. Circuit changes can
          affect this comparison; a distribution shift alone does not establish degraded accuracy.
        </p>
      )}
    </section>
  );
}
