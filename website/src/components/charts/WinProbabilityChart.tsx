"use client";

/**
 * Interactive win-probability chart (B-P1.2).
 *
 * Replaces the static win-probability PNG with a horizontal-bar
 * recharts visualisation.  Bars are coloured by team and reordered
 * by win probability.  Hover shows the precise % + the model's
 * raw vs calibrated probability (when both are present).
 *
 * Falls back gracefully (renders nothing) when the round has no
 * win-probability data — e.g. pre-quali rounds where the model
 * hasn't published a P(win) column yet.
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type { ClassificationEntry } from "@/types";

interface ChartRow {
  driver: string;
  team: string;
  teamColor: string;
  winProbability: number;
  simulatorWinProbability: number | null;
  predictionIntervalLow: number | null;
  predictionIntervalHigh: number | null;
  predictedTime: number;
}

function buildRows(classification: ClassificationEntry[]): ChartRow[] {
  return classification
    .map((c) => {
      const cTyped = c as ClassificationEntry & {
        simulatorWinProbability?: number;
        predictionIntervalLow?: number;
        predictionIntervalHigh?: number;
      };
      return {
        driver: cTyped.driver,
        team: cTyped.team,
        teamColor: cTyped.teamColor || "#888",
        winProbability: typeof cTyped.winProbability === "number" ? cTyped.winProbability : 0,
        simulatorWinProbability:
          typeof cTyped.simulatorWinProbability === "number"
            ? cTyped.simulatorWinProbability * 100
            : null,
        predictionIntervalLow:
          typeof cTyped.predictionIntervalLow === "number" ? cTyped.predictionIntervalLow : null,
        predictionIntervalHigh:
          typeof cTyped.predictionIntervalHigh === "number" ? cTyped.predictionIntervalHigh : null,
        predictedTime: typeof cTyped.predictedTime === "number" ? cTyped.predictedTime : 0,
      };
    })
    .filter((r) => r.winProbability > 0)
    .sort((a, b) => b.winProbability - a.winProbability)
    .slice(0, 12);
}

interface TooltipPayload {
  active?: boolean;
  payload?: Array<{ payload: ChartRow }>;
}

function CustomTooltip({ active, payload }: TooltipPayload) {
  if (!active || !payload || !payload[0]) return null;
  const row = payload[0].payload;
  return (
    <div
      className="rounded-[8px] border p-3 shadow-lg"
      style={{
        background: "var(--surface-elevated)",
        borderColor: "var(--border-strong)",
      }}
    >
      <div className="mb-1 flex items-center gap-2">
        <span
          className="inline-block h-2 w-3 rounded-[2px]"
          style={{ background: row.teamColor }}
          aria-hidden
        />
        <span className="font-bold text-[color:var(--text-primary)]">{row.driver}</span>
        <span className="text-xs text-[color:var(--text-muted)]">{row.team}</span>
      </div>
      <div className="font-mono font-tabular text-2xl font-bold text-[color:var(--accent-live)]">
        {row.winProbability.toFixed(1)}%
      </div>
      {row.simulatorWinProbability !== null && (
        <div className="mt-1 text-xs text-[color:var(--text-secondary)]">
          Simulator: <span className="font-mono font-tabular">{row.simulatorWinProbability.toFixed(1)}%</span>
        </div>
      )}
      <div className="mt-1 text-xs text-[color:var(--text-muted)]">
        Predicted lap:{" "}
        <span className="font-mono font-tabular">{row.predictedTime.toFixed(3)}s</span>
        {row.predictionIntervalLow !== null && row.predictionIntervalHigh !== null && (
          <>
            {" "}
            <span className="text-[color:var(--text-muted)]">
              [{row.predictionIntervalLow.toFixed(2)}–{row.predictionIntervalHigh.toFixed(2)}]
            </span>
          </>
        )}
      </div>
    </div>
  );
}

export default function WinProbabilityChart({
  classification,
}: {
  classification: ClassificationEntry[];
}) {
  const rows = useMemo(() => buildRows(classification), [classification]);
  if (rows.length === 0) return null;
  const chartHeight = Math.max(220, 28 * rows.length + 40);
  return (
    <Card>
      <CardHeader className="gap-2">
        <Badge variant="live" className="self-start">Interactive</Badge>
        <CardTitle>Win Probability</CardTitle>
        <CardDescription>
          Model-derived P(win) for the top {rows.length}. Hover any bar for raw probability,
          simulator probability, and the prediction interval.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div style={{ width: "100%", height: chartHeight }}>
          <ResponsiveContainer>
            <BarChart
              data={rows}
              layout="vertical"
              margin={{ top: 4, right: 24, left: 8, bottom: 4 }}
            >
              <XAxis
                type="number"
                domain={[0, "dataMax"]}
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "var(--border)" }}
                tickFormatter={(v) => `${v.toFixed(0)}%`}
              />
              <YAxis
                type="category"
                dataKey="driver"
                tick={{ fill: "var(--text-secondary)", fontSize: 12, fontWeight: 700 }}
                width={64}
                axisLine={{ stroke: "var(--border)" }}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ fill: "color-mix(in srgb, var(--accent-live) 10%, transparent)" }}
              />
              <Bar dataKey="winProbability" radius={[0, 4, 4, 0]}>
                {rows.map((row) => (
                  <Cell key={row.driver} fill={row.teamColor} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
