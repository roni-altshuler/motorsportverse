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
import type { DriverStanding } from "@/types";
import { computeForecast } from "@/lib/standingsForecast";

interface Props {
  data: DriverStanding[];
  /** Completed rounds, e.g. [1,2,3,4,5]. */
  rounds: number[];
  /** Total rounds in the season (e.g. 22). Used to extend the x-axis + forecast. */
  totalRounds?: number;
}

type ChartRow = Record<string, number | string | null>;

export default function StandingsChart({ data, rounds, totalRounds = 22 }: Props) {
  if (!data.length || !rounds.length) return null;

  const maxCompleted = rounds[rounds.length - 1] ?? rounds.length;
  const forecast = computeForecast(data, totalRounds);

  // Build one row per round across the FULL season scale (R1..R{totalRounds}).
  // Each driver gets two series: `<code>_actual` (solid) and `<code>_forecast`
  // (dashed). Null elsewhere so the lines break cleanly with connectNulls=false.
  const chartData: ChartRow[] = [];
  for (let r = 1; r <= totalRounds; r++) {
    const row: ChartRow = { round: `R${r}` };
    for (const d of data) {
      const hist = d.pointsHistory ?? [];
      const lastIdx = findLastNonNullIndex(hist);
      const completedForDriver = lastIdx + 1;
      const actualKey = `${d.driver}_actual`;
      const forecastKey = `${d.driver}_forecast`;

      if (r <= completedForDriver) {
        row[actualKey] = hist[r - 1] ?? null;
        row[forecastKey] = null;
      } else {
        row[actualKey] = null;
        // Bridge: at the join point (r === completedForDriver + 1) emit both
        // the last actual AND the first forecast so the segments connect.
        const projected = forecast[d.driver] ?? [];
        const projIdx = r - completedForDriver - 1;
        row[forecastKey] = projected[projIdx] ?? null;
      }
    }
    // Bridge point: at r === completedForDriver, emit the last cumulative
    // value into BOTH series so the dashed segment starts attached to the
    // tip of the solid line.
    for (const d of data) {
      const hist = d.pointsHistory ?? [];
      const lastIdx = findLastNonNullIndex(hist);
      const completedForDriver = lastIdx + 1;
      if (r === completedForDriver) {
        row[`${d.driver}_forecast`] = hist[lastIdx] ?? null;
      }
    }
    chartData.push(row);
  }

  return (
    <div className="w-full">
      <ChartLegend drivers={data} />
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
            <YAxis
              stroke="var(--text-muted)"
              fontSize={12}
              tickLine={false}
              axisLine={false}
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
              labelStyle={{ color: "var(--muted)", letterSpacing: "1px", textTransform: "uppercase" }}
              formatter={(value, name) => {
                if (value == null) return [null, null];
                const code = String(name).replace(/_(actual|forecast)$/, "");
                const isForecast = String(name).endsWith("_forecast");
                return [Math.round(Number(value)), isForecast ? `${code} (proj)` : code];
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
            {data.map((d) => (
              <Line
                key={`${d.driver}_actual`}
                type="monotone"
                dataKey={`${d.driver}_actual`}
                stroke={d.teamColor}
                strokeWidth={2.5}
                dot={{ fill: d.teamColor, r: 3 }}
                activeDot={{ r: 5, strokeWidth: 0 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
            {data.map((d) => (
              <Line
                key={`${d.driver}_forecast`}
                type="monotone"
                dataKey={`${d.driver}_forecast`}
                stroke={d.teamColor}
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

function ChartLegend({ drivers }: { drivers: DriverStanding[] }) {
  return (
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
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {drivers.map((d) => (
          <span key={d.driver} className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{ background: d.teamColor }}
            />
            <span style={{ color: "var(--text)" }}>{d.driver}</span>
          </span>
        ))}
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
