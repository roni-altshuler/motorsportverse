"use client";

import { ConstructorStanding } from "@/types";
import { OrbitingCircles } from "@/components/magicui/orbiting-circles";

interface ConstructorsConstellationProps {
  constructors: ConstructorStanding[];
  seasonYear: number;
}

/**
 * 11-team orbital constellation. Inner static element is the season
 * wordmark; each team gets a circular badge orbiting at one of two
 * radii (alternating to avoid collisions).
 */
export default function ConstructorsConstellation({
  constructors,
  seasonYear,
}: ConstructorsConstellationProps) {
  // Split the 11 teams across 2 rings (5 + 6) so badges don't overlap
  const innerRing = constructors.slice(0, 5);
  const outerRing = constructors.slice(5);

  return (
    <div className="relative w-full h-[460px] overflow-hidden">
      {/* Inner static label */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="flex flex-col items-center gap-1 text-center">
          <span className="display-xl text-[color:var(--ink)] !text-[42px] !leading-none [font-weight:700]">
            {seasonYear}
          </span>
          <span className="caption-uppercase tracking-[0.30em] text-[color:var(--muted)]">
            Championship
          </span>
          <span
            className="inline-block w-12 h-px mt-2"
            style={{ background: "var(--accent-f1-red)" }}
          />
        </div>
      </div>

      {/* Inner ring */}
      {innerRing.map((team, i) => (
        <OrbitingCircles
          key={team.team}
          radius={140}
          duration={28}
          delay={(i / innerRing.length) * 28}
          pathColor="rgba(255,255,255,0.06)"
        >
          <span
            data-team={team.team}
            className="flex items-center justify-center w-12 h-12 rounded-full border text-[11px] font-mono uppercase tracking-[0.10em] text-[color:var(--ink)]"
            style={{
              borderColor: team.teamColor || "var(--hairline-strong)",
              background: "var(--surface-card)",
              boxShadow: `0 0 12px ${team.teamColor || "rgba(255,255,255,0.10)"}40`,
            }}
            title={team.team}
          >
            {teamInitials(team.team)}
          </span>
        </OrbitingCircles>
      ))}

      {/* Outer ring (reverse direction so it doesn't read as repeating) */}
      {outerRing.map((team, i) => (
        <OrbitingCircles
          key={team.team}
          radius={210}
          duration={36}
          delay={(i / outerRing.length) * 36}
          reverse
          pathColor="rgba(255,255,255,0.04)"
        >
          <span
            data-team={team.team}
            className="flex items-center justify-center w-12 h-12 rounded-full border text-[11px] font-mono uppercase tracking-[0.10em] text-[color:var(--ink)]"
            style={{
              borderColor: team.teamColor || "var(--hairline-strong)",
              background: "var(--surface-card)",
              boxShadow: `0 0 12px ${team.teamColor || "rgba(255,255,255,0.10)"}40`,
            }}
            title={team.team}
          >
            {teamInitials(team.team)}
          </span>
        </OrbitingCircles>
      ))}
    </div>
  );
}

function teamInitials(team: string): string {
  const parts = team.split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 3).toUpperCase();
  return parts
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}
