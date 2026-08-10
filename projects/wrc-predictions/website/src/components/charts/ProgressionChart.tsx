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

/**
 * Shared points-progression chart (faithful port of the RaceIQ F1 recharts
 * ProgressionChart). A solid cumulative line per entity up to the latest
 * completed round, then a dashed "projected at current pace" segment from the
 * live cursor out to the final round, landing on `projectedTotal` (the driver's
 * projMean from championship[], or the sum of its drivers' projMeans for teams).
 *
 * The projection is a simple linear ramp from the current total to the projected
 * end-of-season total across the remaining rounds — an honest "current pace"
 * read, NOT a model forecast (per the tech-stack scrub policy the label stays
 * "Projected at current pace").
 */
export interface ProgressionSeries {
  /** Stable id used as the recharts dataKey (driver code or team tag). */
  key: string;
  /** Short label shown in the tooltip + legend. */
  label: string;
  /** Line colour (team colour for both drivers and teams). */
  color: string;
  /** Cumulative points after each completed round. */
  history: readonly (number | null | undefined)[];
  /** Projected end-of-season total for the dashed segment endpoint. */
  projectedTotal: number;
}

interface Props {
  series: ProgressionSeries[];
  /** Completed rounds, e.g. [1,2,3,4,5,6,7]. */
  rounds: number[];
  /** Total rounds in the season (e.g. 13). Extends the x-axis + projection. */
  totalRounds?: number;
  /** Entity legend (driver portraits or team swatches) appended below the
   *  shared solid/dashed line-style key. */
  legend?: ReactNode;
}

type ChartRow = Record<string, number | string | null>;

function findLastNonNullIndex(arr: readonly (number | null | undefined)[]): number {
  for (let i = arr.length - 1; i >= 0; i--) {
    if (arr[i] != null) return i;
  }
  return -1;
}

export default function ProgressionChart({ series, rounds, totalRounds = 13, legend }: Props) {
  if (!series.length || !rounds.length) return null;

  const maxCompleted = rounds[rounds.length - 1] ?? rounds.length;
  const labelByKey = new Map(series.map((s) => [s.key, s.label]));

  // Build one row per round across the FULL season scale (R1..R{totalRounds}).
  // Each entity gets two series: `<key>_actual` (solid) and `<key>_forecast`
  // (dashed). Null elsewhere so the lines break cleanly with connectNulls=false.
  const chartData: ChartRow[] = [];
  for (let r = 1; r <= totalRounds; r++) {
    const row: ChartRow = { round: `R${r}` };
    for (const s of series) {
      const hist = s.history ?? [];
      const lastIdx = findLastNonNullIndex(hist);
      const completed = lastIdx + 1;
      const current = hist[lastIdx] ?? 0;
      const remaining = totalRounds - completed;
      const actualKey = `${s.key}_actual`;
      const forecastKey = `${s.key}_forecast`;

      if (r <= completed) {
        row[actualKey] = hist[r - 1] ?? null;
        // Bridge point: at r === completed, attach the dashed segment to the
        // solid tip so the projection starts where the actual line ends.
        row[forecastKey] = r === completed ? current : null;
      } else {
        row[actualKey] = null;
        // Linear ramp from `current` (at round `completed`) to `projectedTotal`
        // (at round `totalRounds`).
        const t = remaining > 0 ? (r - completed) / remaining : 1;
        row[forecastKey] = current + (s.projectedTotal - current) * t;
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
              stroke="var(--accent)"
              strokeDasharray="2 4"
              label={{
                value: "NOW",
                position: "top",
                fill: "var(--accent)",
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
