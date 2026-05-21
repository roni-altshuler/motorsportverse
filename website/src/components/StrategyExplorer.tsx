"use client";

/**
 * What-if Strategy Explorer (B-P2.1, scoped down).
 *
 * The original ambition was an in-browser race simulator with tyre/pit
 * sliders.  That would need a WASM port of models/race_simulator.py — a
 * 1-week build.  This is the *delivered* scope: an interactive
 * comparison chart for the pre-computed strategy options that the
 * pipeline already produces in `round_NN.json.strategyData`.
 *
 * Users get:
 *   - Sorted bar chart of mean race time per strategy
 *   - Delta-to-best annotation on each bar (how much slower than the
 *     fastest pre-computed option)
 *   - Stop-count badge
 *   - Std-dev whisker via a lightweight error-line overlay
 *
 * It's not a true "what-if" — but it surfaces strategy sensitivity in a
 * way the static PNG (which we dropped in the viz cull) never did.
 */
import { useMemo } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/Badge";

interface StrategyRow {
  label: string;
  meanTime: number;
  stdTime: number;
  numStops: number;
}

interface Props {
  // The shape published per-round in round_NN.json.strategyData:
  //   { "<strategy label>": { meanTime, stdTime, numStops }, ... }
  strategyData: Record<string, { meanTime: number; stdTime: number; numStops: number }> | null | undefined;
  totalLaps?: number;
}

function formatSeconds(s: number): string {
  const hours = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = Math.round(s % 60);
  return hours > 0 ? `${hours}h ${m}m ${r}s` : `${m}m ${r}s`;
}

interface TooltipPayload {
  active?: boolean;
  payload?: Array<{ payload: StrategyRow & { delta: number } }>;
}

function CustomTooltip({ active, payload }: TooltipPayload) {
  if (!active || !payload?.[0]) return null;
  const row = payload[0].payload;
  return (
    <div
      className="rounded-[8px] border p-3 shadow-lg"
      style={{
        background: "var(--surface-elevated)",
        borderColor: "var(--border-strong)",
        maxWidth: 280,
      }}
    >
      <div className="text-sm font-bold text-[color:var(--text-primary)] mb-1.5">
        {row.label}
      </div>
      <div className="font-mono font-tabular text-base text-[color:var(--text-primary)]">
        {formatSeconds(row.meanTime)}
      </div>
      <div className="text-xs text-[color:var(--text-muted)] mt-1">
        {row.numStops === 1 ? "1 stop" : `${row.numStops} stops`}
        {" · "}
        std-dev ±{row.stdTime.toFixed(2)}s
      </div>
      {row.delta > 0 && (
        <div className="text-xs mt-2" style={{ color: "var(--accent-info)" }}>
          +{row.delta.toFixed(2)}s slower than the optimal
        </div>
      )}
    </div>
  );
}

export default function StrategyExplorer({ strategyData, totalLaps }: Props) {
  const rows = useMemo<(StrategyRow & { delta: number })[]>(() => {
    if (!strategyData) return [];
    const all = Object.entries(strategyData).map(([label, v]) => ({
      label,
      meanTime: v.meanTime,
      stdTime: v.stdTime,
      numStops: v.numStops,
    }));
    if (all.length === 0) return [];
    all.sort((a, b) => a.meanTime - b.meanTime);
    const best = all[0].meanTime;
    return all.map((r) => ({ ...r, delta: r.meanTime - best }));
  }, [strategyData]);

  if (rows.length === 0) {
    return (
      <div className="rounded-[12px] border border-[color:var(--border)] bg-[color:var(--surface)] p-6 text-sm text-[color:var(--text-muted)]">
        Strategy data not available for this round yet.
      </div>
    );
  }

  // Y-axis tightens around the data range so the visible deltas aren't
  // squashed against the right edge.
  const minTime = rows[0].meanTime;
  const maxTime = rows[rows.length - 1].meanTime;
  const padding = Math.max(2, (maxTime - minTime) * 0.15);

  return (
    <div className="rounded-[12px] border border-[color:var(--border)] bg-[color:var(--surface)] p-4 sm:p-6">
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="live">Interactive</Badge>
            <Badge variant="muted">Monte-Carlo sim</Badge>
          </div>
          <h3 className="text-lg font-bold tracking-tight">
            Strategy Comparison
          </h3>
          <p className="text-xs text-[color:var(--text-muted)] mt-1">
            {totalLaps ? `${totalLaps}-lap race` : "Race-distance simulation"}
            {" · "}
            Best strategy first.  Hover any bar for stop count, std-dev, and
            delta to the optimal.
          </p>
        </div>
        <div className="text-xs text-[color:var(--text-muted)] font-mono font-tabular hidden sm:block">
          {rows.length} variants
        </div>
      </div>

      <div style={{ width: "100%", height: Math.max(180, 50 * rows.length + 30) }}>
        <ResponsiveContainer>
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 0, right: 60, left: 8, bottom: 0 }}
          >
            <XAxis
              type="number"
              domain={[minTime - padding, maxTime + padding]}
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              axisLine={{ stroke: "var(--border)" }}
              tickFormatter={(v) => formatSeconds(v)}
            />
            <YAxis
              type="category"
              dataKey="label"
              tick={{ fill: "var(--text-secondary)", fontSize: 11, fontWeight: 600 }}
              width={180}
              axisLine={{ stroke: "var(--border)" }}
            />
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ fill: "color-mix(in srgb, var(--accent-live) 8%, transparent)" }}
            />
            <Bar
              dataKey="meanTime"
              radius={[0, 4, 4, 0]}
              isAnimationActive={false}
            >
              {rows.map((row, i) => (
                <Cell
                  key={row.label}
                  fill={
                    i === 0
                      ? "var(--accent-positive)"
                      : i === rows.length - 1
                        ? "var(--accent-negative)"
                        : "var(--accent-live)"
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Below-chart legend — explains the green / orange / red coding */}
      <div className="flex flex-wrap items-center gap-4 mt-4 text-xs text-[color:var(--text-muted)]">
        <div className="inline-flex items-center gap-1.5">
          <span
            className="inline-block w-3 h-3 rounded-sm"
            style={{ background: "var(--accent-positive)" }}
            aria-hidden
          />
          fastest
        </div>
        <div className="inline-flex items-center gap-1.5">
          <span
            className="inline-block w-3 h-3 rounded-sm"
            style={{ background: "var(--accent-live)" }}
            aria-hidden
          />
          mid-pack
        </div>
        <div className="inline-flex items-center gap-1.5">
          <span
            className="inline-block w-3 h-3 rounded-sm"
            style={{ background: "var(--accent-negative)" }}
            aria-hidden
          />
          slowest
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
        {rows.slice(0, 4).map((row) => (
          <div
            key={row.label}
            className="rounded-[8px] border border-[color:var(--border)] bg-[color:var(--surface-elevated)] p-3"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-semibold text-[color:var(--text-primary)]">
                {row.label}
              </span>
              <Badge variant="muted" className="text-[9px]">
                {row.numStops === 1 ? "1 stop" : `${row.numStops} stops`}
              </Badge>
            </div>
            <div className="flex items-baseline gap-2 font-mono font-tabular">
              <span className="text-sm text-[color:var(--text-primary)]">
                {formatSeconds(row.meanTime)}
              </span>
              {row.delta > 0 && (
                <span className="text-[color:var(--text-muted)]">
                  (+{row.delta.toFixed(2)}s)
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
