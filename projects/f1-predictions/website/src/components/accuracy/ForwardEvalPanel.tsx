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

import type { ForwardEvalSummaryData, WalkForwardBlock } from "@/types";
import type { ForwardEvalRoundData } from "@/lib/data";

/**
 * ForwardEvalPanel — the season-long honesty strip.
 *
 * Drives off `forward_eval/summary.json`: every round is scored using only the
 * data available before it, then the model's aggregate is put side-by-side with
 * naive baselines anyone could use without a model. The trend chart plots the
 * model's per-round position error against the qualifying-grid baseline so you
 * can read whether the forecast is getting sharper across the season.
 *
 * Renders nothing when the summary is absent (archived / pre-eval seasons).
 */

const MODEL_COLOR = "var(--accent-f1-red)";
const BASELINE_COLOR = "var(--text-muted)";

// Fixed baseline order + plain-language labels (no implementation detail).
const BASELINE_META: { key: string; name: string; description: string }[] = [
  {
    key: "grid_order",
    name: "Qualifying grid",
    description: "Predict the grid order as the finish.",
  },
  {
    key: "standings_order",
    name: "Championship order",
    description: "Rank drivers by championship points.",
  },
  {
    key: "last_race_winner",
    name: "Previous race",
    description: "Carry the last race's order forward.",
  },
];

type Better = "high" | "low";

interface MetricCol {
  label: string;
  metric: string;
  better: Better;
  format: (v: number) => string;
}

// Columns shared by the model and every baseline block.
const COLS: MetricCol[] = [
  {
    label: "Mean error",
    metric: "mean_position_error",
    better: "low",
    format: (v) => v.toFixed(2),
  },
  {
    label: "Order match",
    metric: "spearman_correlation",
    better: "high",
    format: (v) => v.toFixed(2),
  },
  {
    label: "Winner called",
    metric: "winnerHit",
    better: "high",
    format: (v) => `${(v * 100).toFixed(0)}%`,
  },
  {
    label: "Podium hits",
    metric: "podium_hits",
    better: "high",
    format: (v) => `${v.toFixed(1)}/3`,
  },
  {
    label: "Top-10 overlap",
    metric: "top10_overlap",
    better: "high",
    format: (v) => `${v.toFixed(1)}/10`,
  },
];

function meanOf(block: WalkForwardBlock | undefined, metric: string): number | null {
  const m = block?.metrics?.[metric];
  return m && typeof m.mean === "number" ? m.mean : null;
}

function buildValues(block: WalkForwardBlock | undefined): Record<string, number | null> {
  const out: Record<string, number | null> = {};
  for (const c of COLS) out[c.metric] = meanOf(block, c.metric);
  return out;
}

interface ScoreRow {
  key: string;
  name: string;
  description: string;
  isModel: boolean;
  values: Record<string, number | null>;
}

export default function ForwardEvalPanel({
  summary,
  rounds,
}: {
  summary: ForwardEvalSummaryData | null;
  rounds: ForwardEvalRoundData[];
}) {
  const model = summary?.walkForward?.model;
  if (!summary || !model) return null;

  const baselines = summary.walkForward.baselines ?? {};

  const modelRow: ScoreRow = {
    key: "model",
    name: "RaceIQ model",
    description: "Our published pre-race forecast, frozen after qualifying.",
    isModel: true,
    values: buildValues(model),
  };

  const baselineRows: ScoreRow[] = BASELINE_META.filter((b) => baselines[b.key]).map((b) => ({
    key: b.key,
    name: b.name,
    description: b.description,
    isModel: false,
    values: buildValues(baselines[b.key]),
  }));

  const rows = [modelRow, ...baselineRows];
  if (rows.length < 2) return null;

  // Column-wise winners; best value is highlighted regardless of which row owns
  // it (a baseline beating the model is shown honestly).
  const best: Record<string, number | null> = {};
  for (const c of COLS) {
    const vals = rows.map((r) => r.values[c.metric]).filter((v): v is number => v != null);
    best[c.metric] = vals.length ? (c.better === "high" ? Math.max(...vals) : Math.min(...vals)) : null;
  }

  const cellStyle = (value: number | null, bestValue: number | null) => ({
    color: value != null && bestValue != null && value === bestValue ? "var(--success)" : "var(--text)",
    fontWeight: value != null && bestValue != null && value === bestValue ? 700 : 400,
  });

  // "Getting better?" read from the OLS slope of the model's mean position
  // error across rounds. Error falling over the season => sharper forecasts.
  const errTrend = model.metrics?.mean_position_error?.trend ?? null;
  const trendVerdict =
    errTrend == null
      ? null
      : errTrend < -0.05
        ? { label: "Trending sharper", tone: "good" as const }
        : errTrend > 0.05
          ? { label: "Trending softer", tone: "bad" as const }
          : { label: "Holding steady", tone: "neutral" as const };
  const trendPill =
    trendVerdict?.tone === "good"
      ? { background: "rgba(95,166,87,0.14)", color: "var(--success)" }
      : trendVerdict?.tone === "bad"
        ? { background: "rgba(225,6,0,0.12)", color: "#E10600" }
        : { background: "rgba(136,136,136,0.12)", color: "var(--text-muted)" };

  // Per-round trend series: model vs the qualifying-grid baseline.
  const chartData = rounds
    .map((r) => {
      const modelErr = r.mean_position_error;
      const gridErr = r.baselines?.grid_order?.mean_position_error;
      if (modelErr == null) return null;
      return {
        round: `R${r.round}`,
        model: modelErr,
        grid: gridErr ?? null,
      };
    })
    .filter((d): d is { round: string; model: number; grid: number | null } => d !== null);

  const modelMean = meanOf(model, "mean_position_error");
  const hasGrid = chartData.some((d) => d.grid != null);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="section-heading mb-1">Season-Long Track Record</h2>
          <p className="text-sm max-w-2xl" style={{ color: "var(--text-muted)" }}>
            Every round is graded using only the data known before it, then averaged across the{" "}
            {summary.roundsEvaluated} round{summary.roundsEvaluated !== 1 ? "s" : ""} run so far. The
            model sits next to strategies that need no model at all — the best figure in each column
            is highlighted, even when a baseline wins it.
          </p>
        </div>
        {trendVerdict && (
          <span
            className="text-xs font-bold uppercase tracking-wider px-2 py-1 rounded-full whitespace-nowrap"
            style={trendPill}
          >
            {trendVerdict.label}
          </span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th
                className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider whitespace-nowrap"
                style={{ color: "var(--text-muted)" }}
              >
                Strategy
              </th>
              {COLS.map((c) => (
                <th
                  key={c.metric}
                  className="px-4 py-3 text-left text-xs font-bold uppercase tracking-wider whitespace-nowrap"
                  style={{ color: "var(--text-muted)" }}
                >
                  {c.label}
                </th>
              ))}
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
                  <p className="font-bold flex items-center gap-2" style={{ color: "var(--text)" }}>
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
                {COLS.map((c) => {
                  const v = row.values[c.metric];
                  return (
                    <td
                      key={c.metric}
                      className="px-4 py-3 font-mono whitespace-nowrap"
                      style={cellStyle(v, best[c.metric])}
                    >
                      {v != null ? c.format(v) : "–"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs mt-3 leading-relaxed" style={{ color: "var(--text-muted)" }}>
        <strong style={{ color: "var(--text)" }}>Mean error</strong> is how many positions off the
        forecast lands on average (lower is better); <strong style={{ color: "var(--text)" }}>order
        match</strong> rates how closely the predicted running order tracks the real one (1.0 is
        perfect). The qualifying grid stays a genuinely strong yardstick — publishing it beside the
        model keeps the comparison honest.
      </p>

      {chartData.length > 1 && (
        <div className="mt-8">
          <div className="mb-3">
            <h3 className="font-bold text-sm uppercase tracking-wider" style={{ color: "var(--text)" }}>
              Position Error, Round by Round
            </h3>
            <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
              How far the finishing forecast landed from the real result each round — lower is a
              closer call.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 mb-3 text-[11px] font-mono tracking-[0.12em] uppercase text-[color:var(--text-muted)]">
            <span className="inline-flex items-center gap-2" style={{ color: "var(--accent-f1-red)" }}>
              <svg width="24" height="6" aria-hidden>
                <line x1="0" y1="3" x2="24" y2="3" stroke="currentColor" strokeWidth="2.5" />
              </svg>
              RaceIQ model
            </span>
            {hasGrid && (
              <span className="inline-flex items-center gap-2">
                <svg width="24" height="6" aria-hidden>
                  <line
                    x1="0"
                    y1="3"
                    x2="24"
                    y2="3"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeDasharray="5 5"
                    strokeOpacity="0.8"
                  />
                </svg>
                Qualifying grid
              </span>
            )}
          </div>
          <div className="w-full h-72">
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
                  width={36}
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
                  formatter={(value, name) => {
                    if (value == null) return [null, null];
                    const label = name === "model" ? "RaceIQ model" : "Qualifying grid";
                    return [Number(value).toFixed(2), label];
                  }}
                />
                {modelMean != null && (
                  <ReferenceLine
                    y={modelMean}
                    stroke="var(--accent-f1-red)"
                    strokeDasharray="2 4"
                    strokeOpacity={0.5}
                    label={{
                      value: "season avg",
                      position: "right",
                      fill: "var(--accent-f1-red)",
                      fontSize: 9,
                      fontFamily: "var(--font-mono)",
                      letterSpacing: "0.12em",
                    }}
                  />
                )}
                {hasGrid && (
                  <Line
                    type="monotone"
                    dataKey="grid"
                    stroke={BASELINE_COLOR}
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    strokeOpacity={0.85}
                    dot={{ fill: BASELINE_COLOR, r: 2.5 }}
                    activeDot={{ r: 4, strokeWidth: 0 }}
                    connectNulls
                    isAnimationActive={false}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="model"
                  stroke={MODEL_COLOR}
                  strokeWidth={2.5}
                  dot={{ fill: MODEL_COLOR, r: 3 }}
                  activeDot={{ r: 5, strokeWidth: 0 }}
                  connectNulls
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
