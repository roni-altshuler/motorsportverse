"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
  ReferenceLine,
} from "recharts";

interface RoundEntry {
  round: number;
  season?: number;
  drivers_compared: number;
  mean_position_error: number;
  median_position_error: number;
  rmse_position_error: number;
  exact_matches: number;
  within_3: number;
  within_5: number;
  winner_hit: boolean;
  podium_hits: number;
  spearman_correlation: number | null;
  ndcg_at_5: number;
}

interface SeasonSummary {
  rounds_evaluated: number;
  season_mean_error: number | null;
  season_median_error: number | null;
  winner_hit_rate: number | null;
  podium_hit_rate: number | null;
  exact_match_rate: number | null;
  within_3_rate: number | null;
  within_5_rate: number | null;
  mean_spearman: number | null;
  mean_ndcg_at_5: number | null;
}

interface SeasonBlock {
  season: number;
  summary: SeasonSummary;
  rounds: RoundEntry[];
}

interface DriverEntry {
  driver: string;
  rounds: number;
  mae: number;
  within_3_rate: number;
}

interface ReliabilityBucket {
  predicted_lo: number;
  predicted_hi: number;
  samples: number;
  mean_proximity: number;
  mean_actual: number;
}

interface BacktestPayload {
  seasons: number[];
  perSeason: SeasonBlock[];
  perDriver: DriverEntry[];
  reliability: ReliabilityBucket[];
  totalRows: number;
  scoring?: string;
}

type Tab = "overview" | "rounds" | "drivers" | "calibration";

const PREFIX = process.env.NEXT_PUBLIC_BASE_PATH || "";

const PCT = (v: number | null | undefined, digits = 0) =>
  v == null ? "—" : `${(v * 100).toFixed(digits)}%`;
const FIX = (v: number | null | undefined, digits = 2) =>
  v == null ? "—" : v.toFixed(digits);

export default function HistoricalBacktestPanel() {
  const [data, setData] = useState<BacktestPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [activeSeason, setActiveSeason] = useState<number | null>(null);

  useEffect(() => {
    fetch(`${PREFIX}/data/historical_backtest/summary.json`)
      .then((r) => {
        if (!r.ok) throw new Error("not available");
        return r.json();
      })
      .then((d: BacktestPayload) => {
        setData(d);
        setActiveSeason(d.seasons[d.seasons.length - 1] ?? null);
      })
      .catch(() => setError("Historical backtest not available yet."));
  }, []);

  if (error) {
    return (
      <div className="card p-6 text-center">
        <p className="eyebrow mb-2">Backtest not loaded</p>
        <p className="body-sm text-[color:var(--text-muted)]">
          Historical evaluation will publish after the next data refresh.
        </p>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="card p-6 text-center">
        <p className="loading-pulse text-[color:var(--text-muted)]">
          Loading historical evaluation…
        </p>
      </div>
    );
  }

  const seasonBlock =
    data.perSeason.find((s) => s.season === activeSeason) ?? data.perSeason[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="eyebrow mb-1">Historical Performance</p>
          <h3 className="title-md" style={{ color: "var(--text)" }}>
            Backtest across {data.totalRows.toLocaleString()} driver-rounds
          </h3>
          <p className="body-sm mt-1 max-w-2xl" style={{ color: "var(--text-muted)" }}>
            Predicted finishing order scored against the official classification
            for {data.seasons.join(" + ")} — every round, every driver. Numbers
            below are leak-safe: each round was scored using only signals
            available before lights out.
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {data.seasons.map((s) => (
            <button
              key={s}
              onClick={() => setActiveSeason(s)}
              className="px-3 py-1.5 text-xs uppercase tracking-[0.18em] font-mono rounded-md border transition-colors"
              style={{
                background:
                  s === activeSeason
                    ? "color-mix(in srgb, var(--accent-live) 16%, transparent)"
                    : "var(--surface-card)",
                borderColor:
                  s === activeSeason
                    ? "var(--accent-live)"
                    : "var(--hairline)",
                color: s === activeSeason ? "var(--text)" : "var(--text-muted)",
              }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Tab nav */}
      <div className="flex gap-3 border-b border-[color:var(--hairline)] overflow-x-auto">
        {([
          { key: "overview", label: "Season Overview" },
          { key: "rounds", label: "Round-by-Round" },
          { key: "drivers", label: "Per Driver" },
          { key: "calibration", label: "Reliability" },
        ] as { key: Tab; label: string }[]).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className="px-3 py-2 text-xs uppercase tracking-[0.18em] font-mono whitespace-nowrap"
            style={{
              color: tab === t.key ? "var(--text)" : "var(--text-muted)",
              borderBottom: `2px solid ${
                tab === t.key ? "var(--accent-live)" : "transparent"
              }`,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab block={seasonBlock} />}
      {tab === "rounds" && <RoundsTab block={seasonBlock} />}
      {tab === "drivers" && <DriversTab drivers={data.perDriver} />}
      {tab === "calibration" && (
        <CalibrationTab buckets={data.reliability} block={seasonBlock} />
      )}
    </div>
  );
}

function OverviewTab({ block }: { block: SeasonBlock }) {
  const s = block.summary;
  const cards = [
    { label: "Rounds Evaluated", value: s.rounds_evaluated, format: "int" as const },
    { label: "Mean Position Error", value: s.season_mean_error, format: "fix" as const, suffix: " pos" },
    { label: "Within 3 Positions", value: s.within_3_rate, format: "pct" as const, digits: 1 },
    { label: "Within 5 Positions", value: s.within_5_rate, format: "pct" as const, digits: 1 },
    { label: "Podium Hit Rate", value: s.podium_hit_rate, format: "pct" as const, digits: 1 },
    { label: "Winner Hit Rate", value: s.winner_hit_rate, format: "pct" as const, digits: 1 },
    { label: "Order Agreement", value: s.mean_spearman, format: "fix" as const, digits: 3 },
    { label: "Top-5 Ranking Score", value: s.mean_ndcg_at_5, format: "fix" as const, digits: 3 },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {cards.map((c) => (
        <div
          key={c.label}
          className="card p-4"
          style={{
            background:
              "color-mix(in srgb, var(--surface-card) 90%, var(--accent-live))",
          }}
        >
          <p className="eyebrow text-[10px] mb-1">{c.label}</p>
          <p
            className="text-2xl font-black font-mono font-tabular"
            style={{ color: "var(--text)" }}
          >
            {c.value == null
              ? "—"
              : c.format === "pct"
              ? PCT(c.value as number, c.digits ?? 0)
              : c.format === "fix"
              ? FIX(c.value as number, c.digits ?? 2)
              : c.value}
            {c.suffix && (
              <span className="text-xs ml-1 text-[color:var(--text-muted)]">
                {c.suffix}
              </span>
            )}
          </p>
        </div>
      ))}
    </div>
  );
}

function RoundsTab({ block }: { block: SeasonBlock }) {
  const data = useMemo(
    () =>
      block.rounds.map((r) => ({
        round: r.round,
        mae: Number(r.mean_position_error.toFixed(2)),
        spearman: r.spearman_correlation ?? 0,
        podium: r.podium_hits,
        within3: r.within_3,
        within5: r.within_5,
      })),
    [block.rounds],
  );

  const meanMAE = useMemo(
    () =>
      data.length === 0
        ? 0
        : data.reduce((acc, r) => acc + r.mae, 0) / data.length,
    [data],
  );

  return (
    <div className="space-y-6">
      <div className="card p-4 sm:p-5">
        <p className="eyebrow mb-3">Position-Error Trend — {block.season}</p>
        <div style={{ width: "100%", height: 260 }}>
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.06)"
              />
              <XAxis
                dataKey="round"
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--hairline)" }}
              />
              <YAxis
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--hairline)" }}
                label={{
                  value: "MAE (positions)",
                  angle: -90,
                  position: "insideLeft",
                  fill: "var(--text-muted)",
                  fontSize: 11,
                }}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--surface-card)",
                  border: "1px solid var(--hairline)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                }}
              />
              <ReferenceLine
                y={meanMAE}
                stroke="var(--accent-live)"
                strokeDasharray="4 4"
                label={{
                  value: `season mean ${meanMAE.toFixed(2)}`,
                  fill: "var(--accent-live)",
                  fontSize: 10,
                  position: "right",
                }}
              />
              <Line
                type="monotone"
                dataKey="mae"
                stroke="var(--accent-live)"
                strokeWidth={2.2}
                dot={{ r: 3, fill: "var(--accent-live)" }}
                animationDuration={700}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card p-4 sm:p-5">
        <p className="eyebrow mb-3">Podium Hits per Round</p>
        <div style={{ width: "100%", height: 220 }}>
          <ResponsiveContainer>
            <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.06)"
              />
              <XAxis
                dataKey="round"
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--hairline)" }}
              />
              <YAxis
                domain={[0, 3]}
                ticks={[0, 1, 2, 3]}
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--hairline)" }}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--surface-card)",
                  border: "1px solid var(--hairline)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                }}
              />
              <Bar dataKey="podium" animationDuration={700}>
                {data.map((r) => (
                  <Cell
                    key={r.round}
                    fill={
                      r.podium === 3
                        ? "var(--accent-positive)"
                        : r.podium === 2
                        ? "var(--accent-podium-2)"
                        : r.podium === 1
                        ? "var(--accent-podium-3)"
                        : "var(--muted)"
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function DriversTab({ drivers }: { drivers: DriverEntry[] }) {
  const top = useMemo(() => drivers.slice(0, 12), [drivers]);
  const bottom = useMemo(() => drivers.slice(-6).reverse(), [drivers]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <DriverList
        title="Easiest Drivers to Predict"
        subtitle="Lowest mean position error across the backtest"
        rows={top}
        accent="var(--accent-positive)"
      />
      <DriverList
        title="Hardest Drivers to Predict"
        subtitle="Highest mean position error"
        rows={bottom}
        accent="var(--accent-live)"
      />
    </div>
  );
}

function DriverList({
  title,
  subtitle,
  rows,
  accent,
}: {
  title: string;
  subtitle: string;
  rows: DriverEntry[];
  accent: string;
}) {
  const maxMAE = Math.max(...rows.map((r) => r.mae), 1);
  return (
    <div className="card p-4 sm:p-5">
      <p className="eyebrow mb-1">{title}</p>
      <p
        className="text-xs mb-4"
        style={{ color: "var(--text-muted)" }}
      >
        {subtitle}
      </p>
      <ol className="space-y-2">
        {rows.map((r) => (
          <li
            key={r.driver}
            className="grid grid-cols-[64px_1fr_auto] items-center gap-3"
          >
            <span
              className="font-display font-bold tracking-[0.04em] uppercase text-sm"
              style={{ color: "var(--text)" }}
            >
              {r.driver}
            </span>
            <div
              className="relative h-2 rounded-full overflow-hidden"
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border)",
              }}
            >
              <div
                className="absolute inset-y-0 left-0"
                style={{
                  background: accent,
                  width: `${(r.mae / maxMAE) * 100}%`,
                  boxShadow: `0 0 8px color-mix(in srgb, ${accent} 60%, transparent)`,
                }}
              />
            </div>
            <span
              className="font-mono font-tabular text-xs whitespace-nowrap"
              style={{ color: "var(--text-muted)" }}
            >
              MAE <span className="text-[color:var(--text)] font-bold">{r.mae.toFixed(2)}</span>
              <span className="ml-2 opacity-60">{r.rounds} rds</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function CalibrationTab({
  buckets,
  block,
}: {
  buckets: ReliabilityBucket[];
  block: SeasonBlock;
}) {
  // Build a scatter dataset: predicted bucket midpoint vs mean actual.
  // Perfect calibration sits on the y = x diagonal.
  const scatterData = useMemo(
    () =>
      buckets.map((b) => ({
        predicted: (b.predicted_lo + b.predicted_hi) / 2,
        actual: b.mean_actual,
        samples: b.samples,
        proximity: b.mean_proximity,
        label: `P${b.predicted_lo}–P${b.predicted_hi}`,
      })),
    [buckets],
  );

  const maxAxis = Math.ceil(
    Math.max(...scatterData.map((p) => Math.max(p.predicted, p.actual)), 1),
  );

  // Spearman trend across rounds — a smoothed view of rank-correlation
  // stability over the season.
  const spearmanTrend = useMemo(
    () =>
      block.rounds
        .filter((r) => r.spearman_correlation !== null)
        .map((r) => ({
          round: r.round,
          spearman: Number(r.spearman_correlation!.toFixed(3)),
        })),
    [block.rounds],
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="card p-4 sm:p-5">
        <p className="eyebrow mb-1">Predicted vs Actual Calibration</p>
        <p
          className="text-xs mb-3"
          style={{ color: "var(--text-muted)" }}
        >
          Points on the dashed diagonal mean the model&apos;s predicted
          finishing position is matched by the average actual finish for
          drivers in that bucket. Points above the diagonal mean the
          model is too optimistic; below means too pessimistic.
        </p>
        <div style={{ width: "100%", height: 280 }}>
          <ResponsiveContainer>
            <ScatterChart margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.06)"
              />
              <XAxis
                type="number"
                dataKey="predicted"
                domain={[0, maxAxis]}
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--hairline)" }}
                label={{
                  value: "Predicted finishing position",
                  position: "insideBottom",
                  offset: -2,
                  fill: "var(--text-muted)",
                  fontSize: 10,
                }}
              />
              <YAxis
                type="number"
                dataKey="actual"
                domain={[0, maxAxis]}
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--hairline)" }}
                label={{
                  value: "Mean actual finish",
                  angle: -90,
                  position: "insideLeft",
                  fill: "var(--text-muted)",
                  fontSize: 10,
                }}
              />
              <ZAxis dataKey="samples" range={[60, 360]} />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                contentStyle={{
                  background: "var(--surface-card)",
                  border: "1px solid var(--hairline)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                }}
              />
              <ReferenceLine
                segment={[
                  { x: 0, y: 0 },
                  { x: maxAxis, y: maxAxis },
                ]}
                stroke="var(--accent-live)"
                strokeDasharray="4 4"
              />
              <Scatter data={scatterData} fill="var(--accent-podium-1)" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card p-4 sm:p-5">
        <p className="eyebrow mb-1">Finishing-Order Agreement — {block.season}</p>
        <p
          className="text-xs mb-3"
          style={{ color: "var(--text-muted)" }}
        >
          How closely the predicted finishing order matched the actual
          finishing order, round-by-round. Higher and steadier is
          better; the dip rounds are where strategy and incidents broke
          the ranking.
        </p>
        <div style={{ width: "100%", height: 280 }}>
          <ResponsiveContainer>
            <LineChart
              data={spearmanTrend}
              margin={{ top: 8, right: 12, left: 0, bottom: 8 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.06)"
              />
              <XAxis
                dataKey="round"
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--hairline)" }}
              />
              <YAxis
                domain={[-0.4, 1]}
                ticks={[-0.4, 0, 0.4, 0.7, 1]}
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--hairline)" }}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--surface-card)",
                  border: "1px solid var(--hairline)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                }}
              />
              <ReferenceLine
                y={0}
                stroke="var(--text-muted)"
                strokeDasharray="2 2"
              />
              <Line
                type="monotone"
                dataKey="spearman"
                stroke="var(--accent-positive)"
                strokeWidth={2.2}
                dot={{ r: 3, fill: "var(--accent-positive)" }}
                animationDuration={700}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
