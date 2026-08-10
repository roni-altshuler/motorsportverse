"use client";

/**
 * DriverPointsChart — cumulative championship-points progression for one F2
 * driver. Sourced from `driverStandings[*].pointsHistory` (cumulative points per
 * completed round) via `pointsProgression()`. Team-coloured area line; the
 * tooltip surfaces both the running total and the points scored that round.
 * Non-interactive beyond hover, so it stays cheap on the static export.
 *
 * Ported from the RaceIQ F1 flagship's driver/DriverPointsChart.
 */
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PointsProgressionPoint } from "@/lib/driverData";

interface Props {
  data: PointsProgressionPoint[];
  teamColor: string;
  height?: number;
}

// Local tooltip typing — recharts v3 churned its exported TooltipProps generic,
// so the codebase types custom tooltips locally.
interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: PointsProgressionPoint }>;
}

function PointsTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-none border border-[color:var(--hairline)] bg-[color:var(--surface-card)] px-3 py-2 text-xs shadow-lg">
      <div className="eyebrow mb-1">Round {p.round}</div>
      <div className="font-tabular text-[color:var(--ink)]">
        {p.cumulative} pts total
      </div>
      <div className="font-tabular text-[color:var(--muted)]">
        {p.delta > 0 ? `+${p.delta}` : p.delta} this round
      </div>
    </div>
  );
}

export default function DriverPointsChart({
  data,
  teamColor,
  height = 240,
}: Props) {
  if (data.length === 0) {
    return (
      <div className="body-sm text-[color:var(--muted)] py-8 text-center">
        No points progression yet.
      </div>
    );
  }

  const gradientId = "driver-points-fill";

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={teamColor} stopOpacity={0.35} />
              <stop offset="100%" stopColor={teamColor} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid
            stroke="var(--hairline)"
            strokeDasharray="2 4"
            vertical={false}
          />
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--muted)", fontSize: 10 }}
            axisLine={{ stroke: "var(--hairline)" }}
            tickLine={false}
            interval="preserveStartEnd"
            minTickGap={12}
          />
          <YAxis
            tick={{ fill: "var(--muted)", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            width={32}
            allowDecimals={false}
          />
          <Tooltip
            content={<PointsTooltip />}
            cursor={{ stroke: "var(--hairline)", strokeWidth: 1 }}
          />
          <Area
            type="monotone"
            dataKey="cumulative"
            stroke={teamColor}
            strokeWidth={2.5}
            fill={`url(#${gradientId})`}
            dot={false}
            activeDot={{ r: 4, fill: teamColor, strokeWidth: 0 }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
