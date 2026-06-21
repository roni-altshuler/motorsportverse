"use client";

/**
 * Driver detail sheet (B-P1.3b).
 *
 * Click-to-expand panel showing season form + sparkline for a single driver.
 * Uses the data already shipped in standings.json (`pointsHistory`, points,
 * wins, podiums) so there is no per-driver fetch — the parent passes the
 * standings record in as a prop.
 *
 * Visual: minimal grid (3 stat cells + sparkline).  Matches the rest of the
 * 2026-05-21 redesign — flat surfaces, telemetry-orange accent.
 */
import { useMemo } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type { DriverStanding } from "@/types";

interface Props {
  driver: string;                // 3-letter code, e.g. "VER"
  standings: DriverStanding[];
  fullName?: string;             // override when classification has a richer name
}

export default function DriverDetailSheet({ driver, standings, fullName }: Props) {
  const record = useMemo(
    () => standings.find((d) => d.driver === driver),
    [driver, standings],
  );

  if (!record) {
    return (
      <div className="text-sm text-[color:var(--text-muted)] py-3">
        No season record for {driver} yet.
      </div>
    );
  }

  // The pointsHistory array stores cumulative points per round.  Convert to
  // per-round delta for a more legible "form" signal: 0 = no points scored
  // that round, ≥25 = a win.
  const history = record.pointsHistory ?? [];
  const perRoundDelta = history.map((cum, i) =>
    i === 0 ? cum : cum - history[i - 1],
  );
  const chartData = perRoundDelta.map((delta, i) => ({
    round: `R${i + 1}`,
    delta,
  }));

  const teamColor = record.teamColor || "var(--accent-live)";
  const recentForm = perRoundDelta.slice(-3).reduce((a, b) => a + b, 0);

  return (
    <div
      className="mt-2 mb-2 rounded-[10px] border border-[color:var(--border)] bg-[color:var(--surface-elevated)] p-4 grid gap-4 sm:grid-cols-[1fr_2fr] items-center"
      aria-label={`Season detail for ${record.driverFullName ?? driver}`}
    >
      {/* Left: identity + stats */}
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <span
            className="inline-block h-6 w-1.5 rounded-sm"
            style={{ background: teamColor }}
            aria-hidden
          />
          <div className="min-w-0">
            <div className="text-sm font-bold text-[color:var(--text-primary)]">
              {fullName ?? record.driverFullName ?? driver}
            </div>
            <div className="text-xs text-[color:var(--text-muted)]">
              {record.team} · P{record.position}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="rounded-[8px] border border-[color:var(--border)] py-2">
            <div className="font-mono font-tabular text-lg font-bold">
              {record.points}
            </div>
            <div className="text-[10px] uppercase tracking-[0.1em] text-[color:var(--text-muted)] mt-0.5">
              points
            </div>
          </div>
          <div className="rounded-[8px] border border-[color:var(--border)] py-2">
            <div className="font-mono font-tabular text-lg font-bold">
              {record.wins}
            </div>
            <div className="text-[10px] uppercase tracking-[0.1em] text-[color:var(--text-muted)] mt-0.5">
              wins
            </div>
          </div>
          <div className="rounded-[8px] border border-[color:var(--border)] py-2">
            <div className="font-mono font-tabular text-lg font-bold">
              {record.podiums}
            </div>
            <div className="text-[10px] uppercase tracking-[0.1em] text-[color:var(--text-muted)] mt-0.5">
              podiums
            </div>
          </div>
        </div>
      </div>

      {/* Right: sparkline */}
      <div className="min-w-0">
        <div className="flex items-baseline justify-between mb-1">
          <span className="text-[11px] uppercase tracking-[0.1em] text-[color:var(--text-muted)]">
            Recent form (per-round points)
          </span>
          <span
            className="font-mono font-tabular text-xs font-bold"
            style={{
              color:
                recentForm >= 25
                  ? "var(--accent-positive)"
                  : recentForm >= 10
                    ? "var(--accent-live)"
                    : "var(--text-muted)",
            }}
          >
            last 3 rounds: +{recentForm}
          </span>
        </div>
        <div style={{ width: "100%", height: 64 }}>
          {chartData.length > 0 ? (
            <ResponsiveContainer>
              <LineChart
                data={chartData}
                margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
              >
                <XAxis
                  dataKey="round"
                  tick={{ fill: "var(--text-muted)", fontSize: 9 }}
                  axisLine={false}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis hide domain={[0, 30]} />
                <Line
                  type="monotone"
                  dataKey="delta"
                  stroke={teamColor}
                  strokeWidth={2}
                  dot={{ r: 3, fill: teamColor, strokeWidth: 0 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-xs text-[color:var(--text-muted)] py-4">
              No race results yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
