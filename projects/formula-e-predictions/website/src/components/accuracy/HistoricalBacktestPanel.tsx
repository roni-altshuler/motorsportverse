"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  BacktestSeasonBlock,
  BacktestDriverEntry,
  HistoricalBacktest,
  MarketReliability,
} from "@/types/fe";

type Tab = "overview" | "rounds" | "drivers" | "reliability";

const PREFIX = process.env.NEXT_PUBLIC_BASE_PATH || "";

const MARKET_LABELS: Record<string, string> = {
  win: "Win",
  podium: "Podium",
  top6: "Top 6",
  top10: "Top 10",
};
const MARKET_ORDER = ["win", "podium", "top6", "top10"];

const PCT = (v: number | null | undefined, digits = 0) =>
  v == null ? "—" : `${(v * 100).toFixed(digits)}%`;
const FIX = (v: number | null | undefined, digits = 2) =>
  v == null ? "—" : v.toFixed(digits);

const AXIS = { fill: "var(--ink-muted)", fontSize: 11 } as const;
const TOOLTIP_STYLE = {
  background: "var(--surface)",
  border: "1px solid var(--hairline)",
  fontSize: 12,
  color: "var(--ink)",
} as const;

export default function HistoricalBacktestPanel({
  data,
}: {
  data: HistoricalBacktest;
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const block = data.perSeason[0];
  if (!block) return null;

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "Season Overview" },
    { key: "rounds", label: "Round-by-Round" },
    { key: "drivers", label: "Per Driver" },
    { key: "reliability", label: "Reliability" },
  ];

  return (
    <section className="mt-12">
      <div className="mb-4">
        <p className="eyebrow mb-1">Historical performance</p>
        <h2 className="text-xl font-semibold text-[var(--ink)]">
          Backtest across {data.totalRows.toLocaleString()} driver-rounds
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-muted)]">
          Predicted finishing order scored against the official classification for the{" "}
          {data.season} season — every round, every driver. Each round was replayed using
          only signals available before lights-out, so nothing here is hindsight.
        </p>
      </div>

      <div className="mb-6 flex gap-3 overflow-x-auto border-b border-[var(--hairline)]">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className="whitespace-nowrap px-3 py-2 text-xs font-mono uppercase tracking-[0.18em]"
            style={{
              color: tab === t.key ? "var(--ink)" : "var(--ink-muted)",
              borderBottom: `2px solid ${tab === t.key ? "var(--accent)" : "transparent"}`,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab block={block} />}
      {tab === "rounds" && <RoundsTab block={block} />}
      {tab === "drivers" && <DriversTab drivers={data.perDriver} />}
      {tab === "reliability" && <ReliabilityTab markets={data.markets} />}
    </section>
  );
}

function OverviewTab({ block }: { block: BacktestSeasonBlock }) {
  const s = block.summary;
  const cards = [
    { label: "Rounds Evaluated", value: s.rounds_evaluated, kind: "int" as const },
    { label: "Mean Position Error", value: s.season_mean_error, kind: "fix" as const, suffix: " pos" },
    { label: "Within 3 Positions", value: s.within_3_rate, kind: "pct" as const, digits: 1 },
    { label: "Within 5 Positions", value: s.within_5_rate, kind: "pct" as const, digits: 1 },
    { label: "Podium Hit Rate", value: s.podium_hit_rate, kind: "pct" as const, digits: 1 },
    { label: "Winner Hit Rate", value: s.winner_hit_rate, kind: "pct" as const, digits: 1 },
    { label: "Order Agreement", value: s.mean_spearman, kind: "fix" as const, digits: 3 },
    { label: "Top-5 Ranking", value: s.mean_ndcg_at_5, kind: "fix" as const, digits: 3 },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {cards.map((c) => (
        <div
          key={c.label}
          className="rounded-[var(--radius-md)] border border-[var(--hairline)] bg-[var(--surface)] p-4"
        >
          <p className="mono-label">{c.label}</p>
          <p className="font-display font-tabular mt-1 text-2xl font-bold text-[var(--ink)]">
            {c.value == null
              ? "—"
              : c.kind === "pct"
                ? PCT(c.value as number, c.digits ?? 0)
                : c.kind === "fix"
                  ? FIX(c.value as number, c.digits ?? 2)
                  : c.value}
            {c.suffix && c.value != null && (
              <span className="ml-1 text-xs text-[var(--ink-muted)]">{c.suffix}</span>
            )}
          </p>
        </div>
      ))}
    </div>
  );
}

function RoundsTab({ block }: { block: BacktestSeasonBlock }) {
  const data = useMemo(
    () =>
      block.rounds.map((r) => ({
        round: `R${r.round}`,
        mae: r.mean_position_error ?? 0,
        podium: r.podium_hits,
      })),
    [block.rounds],
  );
  const meanMAE = useMemo(
    () => (data.length ? data.reduce((a, r) => a + r.mae, 0) / data.length : 0),
    [data],
  );

  return (
    <div className="space-y-6">
      <div className="rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-4 sm:p-5">
        <p className="eyebrow mb-3">Position-error trend — {block.season}</p>
        <div style={{ width: "100%", height: 260 }}>
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--hairline)" />
              <XAxis dataKey="round" tick={AXIS} axisLine={{ stroke: "var(--hairline)" }} />
              <YAxis tick={AXIS} axisLine={{ stroke: "var(--hairline)" }} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <ReferenceLine
                y={meanMAE}
                stroke="var(--accent)"
                strokeDasharray="4 4"
                label={{
                  value: `season mean ${meanMAE.toFixed(2)}`,
                  fill: "var(--accent)",
                  fontSize: 10,
                  position: "right",
                }}
              />
              <Line
                type="monotone"
                dataKey="mae"
                name="MAE (positions)"
                stroke="var(--accent)"
                strokeWidth={2.2}
                dot={{ r: 3, fill: "var(--accent)" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-4 sm:p-5">
        <p className="eyebrow mb-3">Podium hits per round</p>
        <div style={{ width: "100%", height: 220 }}>
          <ResponsiveContainer>
            <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--hairline)" />
              <XAxis dataKey="round" tick={AXIS} axisLine={{ stroke: "var(--hairline)" }} />
              <YAxis
                domain={[0, 3]}
                ticks={[0, 1, 2, 3]}
                tick={AXIS}
                axisLine={{ stroke: "var(--hairline)" }}
              />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "var(--surface-2)" }} />
              <Bar dataKey="podium" name="Podium hits">
                {data.map((r) => (
                  <Cell
                    key={r.round}
                    fill={r.podium >= 2 ? "var(--accent)" : r.podium === 1 ? "var(--accent-info)" : "var(--muted)"}
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

function DriversTab({ drivers }: { drivers: BacktestDriverEntry[] }) {
  const top = useMemo(() => drivers.slice(0, 10), [drivers]);
  const bottom = useMemo(() => drivers.slice(-6).reverse(), [drivers]);
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <DriverList
        title="Easiest to predict"
        subtitle="Lowest mean position error across the backtest"
        rows={top}
      />
      <DriverList
        title="Hardest to predict"
        subtitle="Highest mean position error"
        rows={bottom}
      />
    </div>
  );
}

function DriverList({
  title,
  subtitle,
  rows,
}: {
  title: string;
  subtitle: string;
  rows: BacktestDriverEntry[];
}) {
  const maxMAE = Math.max(...rows.map((r) => r.mae), 1);
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-4 sm:p-5">
      <p className="eyebrow mb-1">{title}</p>
      <p className="mb-4 text-xs text-[var(--ink-muted)]">{subtitle}</p>
      <ol className="space-y-2">
        {rows.map((r) => (
          <li key={r.driver} className="grid grid-cols-[52px_1fr_auto] items-center gap-3">
            <span className="font-display text-sm font-bold uppercase tracking-[0.04em] text-[var(--ink)]">
              {r.driver}
            </span>
            <div className="relative h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
              <div
                className="absolute inset-y-0 left-0 rounded-full"
                style={{ background: "var(--accent)", width: `${(r.mae / maxMAE) * 100}%` }}
              />
            </div>
            <span className="whitespace-nowrap font-mono text-xs text-[var(--ink-muted)]">
              MAE <span className="font-bold text-[var(--ink)]">{r.mae.toFixed(2)}</span>
              <span className="ml-2 opacity-60">{r.rounds} rd</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ReliabilityTab({ markets }: { markets: Record<string, MarketReliability> }) {
  const keys = MARKET_ORDER.filter((m) => m in markets);
  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--ink-muted)]">
        Each dot is a bucket of forecasts at a similar probability; its height is how often
        that outcome actually happened. Dots on the dashed diagonal mean the stated
        probabilities held up. Bubble size is the sample count.
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {keys.map((m) => {
          const rep = markets[m];
          return (
            <div
              key={m}
              className="rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-4"
            >
              <div className="mb-3 flex items-baseline justify-between">
                <p className="font-semibold text-[var(--ink)]">{MARKET_LABELS[m] ?? m}</p>
                <p className="font-mono text-xs text-[var(--ink-muted)]">
                  Brier {FIX(rep.brier, 4)} · n {rep.samples}
                </p>
              </div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`${PREFIX}/data/${rep.plot}`}
                alt={`${MARKET_LABELS[m] ?? m} market reliability diagram`}
                loading="lazy"
                className="mx-auto block w-full max-w-[320px]"
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
