"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/**
 * Win-market-by-round chart — the NASCAR adaptation of the F1 flagship's
 * WinProbabilityChart, reshaped around the data FE actually has.
 *
 * F1 charts a single round's win market as bars (it has per-round quali-time
 * ensembles). FE's probability layer re-forecasts every round,
 * so the richer story here is the EVOLUTION: each probabilities/round_NN.json
 * carries the win market exactly as it stood before that round. This chart
 * draws that pre-race win probability per contender across rounds, up to and
 * including the next upcoming round (rounds beyond the next would all show the
 * same conditioning state, so they are honestly excluded).
 *
 * Values are the model's Monte-Carlo win probabilities (`rawProbability` in
 * the market files — the same quantity every other chart on the site labels
 * "win probability"); the calibrated headline number is shown alongside in
 * the tooltip when it differs.
 */
export interface WinTrendPoint {
  /** Model win probability (0..1) before the round; null when unavailable. */
  p: number | null;
  /** Calibrated headline probability (0..1), when the calibrator was fitted. */
  calibrated?: number | null;
}

export interface WinTrendSeries {
  code: string;
  name: string;
  color: string;
  /** One point per entry in `rounds`. */
  points: WinTrendPoint[];
}

export interface WinProbabilityTrend {
  /** Round numbers charted, e.g. [1,2,3,4,5,6]. */
  rounds: number[];
  /** Rounds up to this number are completed; later entries are upcoming. */
  completedRounds: number;
  series: WinTrendSeries[];
}

type ChartRow = Record<string, number | string | null>;

export default function WinProbabilityChart({ trend }: { trend: WinProbabilityTrend }) {
  const { rounds, completedRounds, series } = trend;
  if (!rounds.length || !series.length) return null;

  const byKey = new Map(series.map((s) => [s.code, s]));

  // One row per charted round. Each driver gets a solid line over completed
  // rounds and a dashed bridge to the upcoming round's pre-race forecast
  // (same solid/dashed vocabulary as the standings ProgressionChart).
  const chartData: ChartRow[] = rounds.map((roundNum, i) => {
    const row: ChartRow = { round: `R${roundNum}` };
    for (const s of series) {
      const p = s.points[i]?.p;
      const pct = p == null ? null : p * 100;
      const isCompleted = roundNum <= completedRounds;
      row[`${s.code}_run`] = isCompleted ? pct : null;
      // Bridge point: the dashed segment starts at the last completed round.
      row[`${s.code}_next`] = roundNum >= completedRounds ? pct : null;
      const cal = s.points[i]?.calibrated;
      row[`${s.code}_cal`] = cal == null ? null : cal * 100;
    }
    return row;
  });

  const hasUpcoming = rounds.some((r) => r > completedRounds);
  const lastCompletedLabel = `R${Math.min(completedRounds, rounds[rounds.length - 1])}`;

  return (
    <div className="w-full">
      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-[11px] uppercase tracking-[0.12em] text-[color:var(--muted)]">
        <span className="inline-flex items-center gap-2">
          <svg width="24" height="6" aria-hidden>
            <line x1="0" y1="3" x2="24" y2="3" stroke="currentColor" strokeWidth="2.5" />
          </svg>
          Pre-race forecast · completed rounds
        </span>
        {hasUpcoming && (
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
            Next round
          </span>
        )}
      </div>
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--hairline)" />
            <XAxis
              dataKey="round"
              stroke="var(--muted)"
              fontSize={12}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              stroke="var(--muted)"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}%`}
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
              formatter={(value, name, item) => {
                if (value == null) return [null, null];
                const raw = String(name);
                if (raw.endsWith("_cal")) return [null, null];
                const code = raw.replace(/_(run|next)$/, "");
                const rowData = (item as { payload?: ChartRow } | undefined)?.payload;
                // The `_next` key duplicates the bridge point at the last
                // completed round; hide it there so drivers aren't listed twice.
                if (raw.endsWith("_next") && rowData?.[`${code}_run`] != null) {
                  return [null, null];
                }
                const s = byKey.get(code);
                const cal = rowData?.[`${code}_cal`];
                const calNote =
                  typeof cal === "number" && Math.abs(cal - Number(value)) > 0.05
                    ? ` · calibrated ${cal.toFixed(1)}%`
                    : "";
                return [`${Number(value).toFixed(1)}%${calNote}`, s?.name ?? code];
              }}
            />
            {completedRounds >= rounds[0] && (
              <ReferenceLine
                x={lastCompletedLabel}
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
            )}
            {series.map((s) => (
              <Line
                key={`${s.code}_run`}
                type="monotone"
                dataKey={`${s.code}_run`}
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
                key={`${s.code}_next`}
                type="monotone"
                dataKey={`${s.code}_next`}
                stroke={s.color}
                strokeWidth={2}
                strokeDasharray="5 5"
                strokeOpacity={0.55}
                dot={{ fill: s.color, r: 3, opacity: 0.55 }}
                activeDot={{ r: 4, strokeWidth: 0 }}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
        {series.map((s) => (
          <span key={s.code} className="inline-flex items-center gap-1.5 text-xs text-[var(--ink-muted)]">
            <span className="inline-block h-2 w-3 rounded-sm" style={{ background: s.color }} />
            {s.name}
          </span>
        ))}
      </div>
      <p className="mt-2 text-xs text-[var(--ink-dim)]">
        Each point is the win probability the model published before that round&rsquo;s feature
        race — a forward-time record, never revised after results.
      </p>
    </div>
  );
}
