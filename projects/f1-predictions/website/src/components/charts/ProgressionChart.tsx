"use client";

import type { ReactNode } from "react";
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
import { computeForecastByKey } from "@/lib/standingsForecast";

/** One line on the chart: a driver code or a constructor/team name. */
export interface ProgressionSeries {
  /** Stable id used as the recharts dataKey (driver code or team name). */
  key: string;
  /** Short label shown in the tooltip. */
  label: string;
  /** Line colour (team colour for both drivers and constructors). */
  color: string;
  pointsHistory: readonly (number | null | undefined)[];
}

interface Props {
  series: ProgressionSeries[];
  /** Completed rounds, e.g. [1,2,3,4,5]. */
  rounds: number[];
  /** Total rounds in the season (e.g. 22). Extends the x-axis + forecast. */
  totalRounds?: number;
  /** Entity legend (driver portraits or team swatches) appended below the
   *  shared solid/dashed line-style key. */
  legend?: ReactNode;
}

type ChartRow = Record<string, number | string | null>;

/**
 * Shared points-progression chart: a solid cumulative line per entity up to the
 * latest completed round, then a dashed "projected at current pace" line to the
 * end of the season. Used by both the driver and constructor standings charts.
 */
export default function ProgressionChart({ series, rounds, totalRounds = 22, legend }: Props) {
  if (!series.length || !rounds.length) return null;

  const maxCompleted = rounds[rounds.length - 1] ?? rounds.length;
  const forecast = computeForecastByKey(series, totalRounds);
  const labelByKey = new Map(series.map((s) => [s.key, s.label]));

  // Build one row per round across the FULL season scale (R1..R{totalRounds}).
  // Each entity gets two series: `<key>_actual` (solid) and `<key>_forecast`
  // (dashed). Null elsewhere so the lines break cleanly with connectNulls=false.
  const chartData: ChartRow[] = [];
  for (let r = 1; r <= totalRounds; r++) {
    const row: ChartRow = { round: `R${r}` };
    for (const s of series) {
      const hist = s.pointsHistory ?? [];
      const lastIdx = findLastNonNullIndex(hist);
      const completed = lastIdx + 1;
      const actualKey = `${s.key}_actual`;
      const forecastKey = `${s.key}_forecast`;

      if (r <= completed) {
        row[actualKey] = hist[r - 1] ?? null;
        row[forecastKey] = null;
      } else {
        row[actualKey] = null;
        const projected = forecast[s.key] ?? [];
        const projIdx = r - completed - 1;
        row[forecastKey] = projected[projIdx] ?? null;
      }
    }
    // Bridge point: at r === completed, emit the last cumulative value into the
    // forecast series too so the dashed segment starts attached to the solid tip.
    for (const s of series) {
      const hist = s.pointsHistory ?? [];
      const lastIdx = findLastNonNullIndex(hist);
      if (r === lastIdx + 1) {
        row[`${s.key}_forecast`] = hist[lastIdx] ?? null;
      }
    }
    chartData.push(row);
  }

  return (
    <div className="w-full">
      <div className="flex flex-col gap-2 mb-3 text-[11px] font-mono tracking-[0.12em] uppercase text-[color:var(--text-muted)]">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
          <span className="inline-flex items-center gap-2">
            <svg width="24" height="6" aria-hidden>
              <line x1="0" y1="3" x2="24" y2="3" stroke="currentColor" strokeWidth="2.5" />
            </svg>
            Current standings
          </span>
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
                strokeOpacity="0.7"
              />
            </svg>
            Projected at current pace · refreshes each round
          </span>
        </div>
        {legend}
      </div>
      <div className="w-full h-80">
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
            <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--surface-card)",
                border: "1px solid var(--hairline)",
                borderRadius: 0,
                color: "var(--ink)",
                fontSize: "13px",
                fontFamily: "var(--font-mono)",
              }}
              labelStyle={{ color: "var(--muted)", letterSpacing: "1px", textTransform: "uppercase" }}
              formatter={(value, name) => {
                if (value == null) return [null, null];
                const key = String(name).replace(/_(actual|forecast)$/, "");
                const isForecast = String(name).endsWith("_forecast");
                const label = labelByKey.get(key) ?? key;
                return [Math.round(Number(value)), isForecast ? `${label} (proj)` : label];
              }}
            />
            <ReferenceLine
              x={`R${maxCompleted}`}
              stroke="var(--accent-f1-red)"
              strokeDasharray="2 4"
              label={{
                value: "NOW",
                position: "top",
                fill: "var(--accent-f1-red)",
                fontSize: 10,
                fontFamily: "var(--font-mono)",
                letterSpacing: "0.18em",
              }}
            />
            {series.map((s) => (
              <Line
                key={`${s.key}_actual`}
                type="monotone"
                dataKey={`${s.key}_actual`}
                stroke={s.color}
                strokeWidth={2.5}
                dot={{ fill: s.color, r: 3 }}
                activeDot={{ r: 5, strokeWidth: 0 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
            {series.map((s) => (
              <Line
                key={`${s.key}_forecast`}
                type="monotone"
                dataKey={`${s.key}_forecast`}
                stroke={s.color}
                strokeWidth={2}
                strokeDasharray="5 5"
                strokeOpacity={0.55}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 0 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function findLastNonNullIndex(arr: readonly (number | null | undefined)[]): number {
  for (let i = arr.length - 1; i >= 0; i--) {
    if (arr[i] != null) return i;
  }
  return -1;
}
