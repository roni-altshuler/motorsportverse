"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import type { ClassificationEntry } from "@/types";

interface PredictedPaceChartProps {
  classification: ClassificationEntry[];
  /** Optional cap on number of drivers shown. */
  limit?: number;
}

interface Row {
  driver: string;
  team: string;
  teamColor: string;
  predictedTime: number;
  gapMs: number;
}

function TooltipBody({ active, payload }: { active?: boolean; payload?: Array<{ payload: Row }> }) {
  if (!active || !payload?.[0]) return null;
  const row = payload[0].payload;
  return (
    <div
      className="rounded-none border p-3"
      style={{
        background: "var(--surface-card)",
        borderColor: "var(--hairline)",
        fontFamily: "var(--font-mono)",
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span
          className="inline-block h-2 w-3 rounded-none"
          style={{ background: row.teamColor }}
          aria-hidden
        />
        <span className="title-sm">{row.driver}</span>
        <span className="eyebrow">{row.team}</span>
      </div>
      <div className="font-mono font-tabular text-xl text-[color:var(--ink)]">
        {row.predictedTime.toFixed(3)}s
      </div>
      <div className="eyebrow mt-2">
        Gap to leader: <span className="font-mono">+{(row.gapMs / 1000).toFixed(3)}s</span>
      </div>
    </div>
  );
}

export default function PredictedPaceChart({ classification, limit = 14 }: PredictedPaceChartProps) {
  const rows = useMemo<Row[]>(() => {
    const ordered = [...classification].sort((a, b) => a.predictedTime - b.predictedTime).slice(0, limit);
    const leader = ordered[0]?.predictedTime ?? 0;
    return ordered.map((c) => ({
      driver: c.driver,
      team: c.team,
      teamColor: c.teamColor || "#888",
      predictedTime: c.predictedTime,
      gapMs: Math.max(0, (c.predictedTime - leader) * 1000),
    }));
  }, [classification, limit]);

  if (rows.length === 0) return null;

  return (
    <div style={{ width: "100%", height: "100%", minHeight: 320 }}>
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
          <defs>
            {rows.map((row) => (
              <linearGradient key={row.driver} id={`pace-${row.driver}`} x1="0" x2="1" y1="0" y2="0">
                <stop offset="0%" stopColor={row.teamColor} stopOpacity={0.4} />
                <stop offset="100%" stopColor={row.teamColor} stopOpacity={1} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, "dataMax"]}
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            tickFormatter={(v) => `+${(v / 1000).toFixed(2)}s`}
            axisLine={{ stroke: "var(--border)" }}
          />
          <YAxis
            type="category"
            dataKey="driver"
            tick={{ fill: "var(--text-secondary)", fontSize: 12, fontWeight: 700 }}
            width={64}
            axisLine={{ stroke: "var(--border)" }}
          />
          <Tooltip
            content={<TooltipBody />}
            cursor={{ fill: "color-mix(in srgb, var(--accent-live) 8%, transparent)" }}
          />
          <Bar dataKey="gapMs" radius={[0, 4, 4, 0]} animationDuration={900} animationEasing="ease-out">
            {rows.map((row) => (
              <Cell key={row.driver} fill={`url(#pace-${row.driver})`} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
