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

import type { ModelHealth } from "@/types/nascar";

/**
 * ModelHealthPanel — a small, honest "is the model still healthy?" strip.
 *
 * Reads `model_health.json`. It separates the two things that are easy to
 * conflate: whether the FORECASTS are still landing well (output quality, the
 * rolling win-market Brier trend) versus whether the model's INPUTS have
 * drifted from what it was tuned on. Input drift is watched but does not, on its
 * own, mean the predictions have degraded — so the headline status follows
 * output quality and input shifts are shown as a separate signal.
 *
 * Ported from the RaceIQ F1 ModelHealthPanel, adapted to NASCAR's camelCase
 * model_health.json contract (outputDrift.relativeChange / roundsCompared /
 * rollingBrierBaseline) and the victory-lane yellow accent. Every field is
 * optional; the panel renders only what the file provides and hides entirely
 * when the file is missing.
 */

const FEATURE_LABELS: Record<string, string> = {
  predictedValue: "Predicted finish score",
  pWin: "Win probability",
  pPodium: "Podium probability",
  pTop6: "Top-6 probability",
  pTop10: "Top-10 probability",
  pDnf: "DNF risk",
  meanFinish: "Projected finish",
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
  bad: "var(--accent-f1-red)",
  neutral: "var(--text-muted)",
};

const TONE_PILL: Record<Tone, { background: string; color: string }> = {
  good: { background: "rgba(95,166,87,0.14)", color: "var(--success)" },
  warn: { background: "rgba(212,160,23,0.14)", color: "var(--warning)" },
  bad: { background: "rgba(255,214,89,0.14)", color: "var(--accent-f1-red-bright)" },
  neutral: { background: "rgba(136,136,136,0.12)", color: "var(--text-muted)" },
};

const SEVERITY_LABEL: Record<Tone, string> = {
  good: "Stable",
  warn: "Shifting",
  bad: "Shifted",
  neutral: "Unknown",
};

export default function ModelHealthPanel({ health }: { health: ModelHealth | null }) {
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
  const chartData = trend.map((d) => ({ round: `R${d.round}`, err: d.brier }));

  return (
    <div>
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
        A self-check on the live model: whether recent forecasts are still landing as well as they
        should, and whether the numbers feeding the model have drifted from what it was tuned on.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
        <div className="metric-card">
          <p className="eyebrow mb-2">Forecast quality</p>
          {relPct != null ? (
            <>
              <p
                className="text-2xl font-mono font-bold tracking-tight"
                style={{ color: relBetter ? "var(--success)" : "var(--accent-f1-red-bright)" }}
              >
                {relBetter ? "▼" : "▲"} {relPct.toFixed(0)}%
              </p>
              <p className="text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
                {relBetter ? "lower error than" : "higher error than"} the season benchmark
              </p>
            </>
          ) : (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Not enough graded rounds yet.
            </p>
          )}
        </div>
        <div className="metric-card">
          <p className="eyebrow mb-2">Rounds monitored</p>
          <p className="text-2xl font-mono font-bold tracking-tight" style={{ color: "var(--text)" }}>
            {output?.roundsCompared ?? trend.length ?? "–"}
          </p>
          <p className="text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
            recent rounds in the rolling check
          </p>
        </div>
        <div className="metric-card">
          <p className="eyebrow mb-2">Input drift</p>
          <p
            className="text-2xl font-mono font-bold tracking-tight"
            style={{ color: shiftedCount > 0 ? "var(--warning)" : "var(--success)" }}
          >
            {drift.length > 0 ? `${shiftedCount}/${drift.length}` : "–"}
          </p>
          <p className="text-[11px] mt-1" style={{ color: "var(--text-muted)" }}>
            model inputs that moved vs baseline
          </p>
        </div>
      </div>

      {drift.length > 0 && (
        <div className="mb-6">
          <p className="eyebrow mb-2">Input drift by feature</p>
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
              Win-market Brier, Round by Round
            </h3>
            <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
              How far the model&apos;s win probabilities sat from who actually won — lower is a
              better-calibrated forecast.
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
                    return [Number(value).toFixed(4), "Win Brier"];
                  }}
                />
                {output?.rollingBrierBaseline != null && (
                  <ReferenceLine
                    y={output.rollingBrierBaseline}
                    stroke="var(--text-muted)"
                    strokeDasharray="5 5"
                    strokeOpacity={0.7}
                    label={{
                      value: "benchmark",
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
          Some model inputs have drifted from their reference range — normal across a season as the
          field moves between superspeedways, short tracks, intermediates and road courses. It is
          flagged here for transparency, but the rolling forecast-quality check above shows whether
          the predictions themselves are{" "}
          {outTone === "good" ? "still holding up" : "being watched closely"}.
        </p>
      )}
    </div>
  );
}
