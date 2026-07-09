"use client";

// Dependency-free podium/win probability board — the NASCAR analogue of RaceIQ F1's
// visx PodiumProbabilityChart. For each driver, a faded full-width bar shows
// podium probability with a prominent inset bar for win probability, so the two
// markets read in one glance. Drawn with shared tokens + team colours.
//
// Upgraded to F1-chart-family richness where FE's data allows: driver headshots
// on each row and a native hover tooltip carrying the full market ladder
// (win / podium / top-6 / top-10 + expected finish) when those optional fields
// are passed. Props stay backward compatible with the original win+podium rows.

import { DriverHeadshot } from "@/components/ui/DriverHeadshot";

export interface PodiumRow {
  code: string;
  name: string;
  team: string;
  teamColor: string;
  pWin: number;
  pPodium: number;
  /** Optional richer markets — shown in the row tooltip when present. */
  pTop6?: number;
  pTop10?: number;
  meanFinish?: number;
}

function rowTitle(r: PodiumRow): string {
  const parts = [
    `${r.name} · ${r.team}`,
    `Win ${(r.pWin * 100).toFixed(1)}%`,
    `Podium ${(r.pPodium * 100).toFixed(1)}%`,
  ];
  if (typeof r.pTop6 === "number") parts.push(`Top 6 ${(r.pTop6 * 100).toFixed(1)}%`);
  if (typeof r.pTop10 === "number") parts.push(`Top 10 ${(r.pTop10 * 100).toFixed(1)}%`);
  if (typeof r.meanFinish === "number") parts.push(`Expected finish P${r.meanFinish.toFixed(1)}`);
  return parts.join("\n");
}

export function PodiumProbabilityChart({
  rows,
  title = "Win vs podium probability",
  showHeadshots = true,
}: {
  rows: PodiumRow[];
  title?: string;
  showHeadshots?: boolean;
}) {
  const max = Math.max(0.0001, ...rows.map((r) => r.pPodium));
  const hasLadder = rows.some((r) => typeof r.pTop6 === "number");

  return (
    <div>
      <p className="eyebrow mb-3">{title}</p>
      <div className="flex flex-col gap-2.5">
        {rows.map((r) => (
          <div key={r.code} className="flex items-center gap-3" title={rowTitle(r)}>
            {showHeadshots && <DriverHeadshot code={r.code} teamColor={r.teamColor} size={24} />}
            <span className="w-24 shrink-0 truncate text-sm text-[var(--ink)]" title={r.name}>
              {r.name.split(" ").slice(-1)[0]}
            </span>
            <div className="relative h-6 flex-1 overflow-hidden rounded-[var(--radius-sm)] bg-[var(--surface-2)]">
              {/* podium = faded team-coloured bar */}
              <div
                className="absolute inset-y-0 left-0 rounded-[var(--radius-sm)]"
                style={{
                  width: `${(r.pPodium / max) * 100}%`,
                  backgroundColor: r.teamColor,
                  opacity: 0.32,
                }}
              />
              {/* win = solid prominent bar */}
              <div
                className="absolute inset-y-0 left-0 rounded-[var(--radius-sm)]"
                style={{
                  width: `${(r.pWin / max) * 100}%`,
                  background: `linear-gradient(90deg, ${r.teamColor}, var(--accent))`,
                }}
              />
            </div>
            <span className="font-tabular w-11 shrink-0 text-right text-xs text-[var(--ink)]">
              {(r.pWin * 100).toFixed(0)}%
            </span>
            <span className="font-tabular w-11 shrink-0 text-right text-xs text-[var(--ink-dim)]">
              {(r.pPodium * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
      <div className="mono-label mt-3 flex flex-wrap gap-x-5 gap-y-1">
        <span className="inline-flex items-center gap-1.5 text-[var(--ink-muted)]">
          <span className="inline-block h-2 w-3 rounded-sm" style={{ background: "var(--accent)" }} />
          Win
        </span>
        <span className="inline-flex items-center gap-1.5 text-[var(--ink-muted)]">
          <span
            className="inline-block h-2 w-3 rounded-sm"
            style={{ background: "var(--ink-dim)", opacity: 0.4 }}
          />
          Podium
        </span>
        {hasLadder && (
          <span className="text-[var(--ink-dim)]">Hover a row for the full market ladder</span>
        )}
      </div>
    </div>
  );
}
