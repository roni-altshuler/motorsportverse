"use client";

import { useEffect, useRef, useState } from "react";

import type { TeamStanding } from "@/types/indycar";
import { OrbitingCircles } from "@/components/magicui/orbiting-circles";
import { teamColor as resolveTeamColor } from "@/lib/teams";

interface ConstructorsConstellationProps {
  teams: TeamStanding[];
  seasonYear: number;
}

const MAX_SIZE = 460;
const INNER_RATIO = 0.3;
const OUTER_RATIO = 0.45;

/**
 * Team orbital constellation. Ported from RaceIQ F1's ConstructorsConstellation.
 * IndyCar teams align with the two engine suppliers, so the teams'
 * championship is a real title fight. Each team gets a circular badge orbiting
 * at one of two radii (split across two rings to avoid collisions); container is
 * responsive so badges never spill the viewport on narrow screens. Themed to the
 * IndyCar red accent.
 *
 * Client component (orbiting-circles animates) — fed plain props only, never the
 * fs-based loader.
 */
export default function ConstructorsConstellation({
  teams,
  seasonYear,
}: ConstructorsConstellationProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState(MAX_SIZE);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const width = Math.min(entry.contentRect.width, MAX_SIZE);
        setSize(width);
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Split the teams across 2 rings so badges don't overlap. The first ~45% go
  // on the inner ring, the rest on the outer ring (reversed direction).
  const split = Math.ceil(teams.length / 2);
  const innerRing = teams.slice(0, split);
  const outerRing = teams.slice(split);
  const innerR = Math.round(size * INNER_RATIO);
  const outerR = Math.round(size * OUTER_RATIO);

  const colorFor = (team: TeamStanding) => team.teamColor || resolveTeamColor(team.team);

  return (
    <div
      ref={containerRef}
      className="relative mx-auto aspect-square w-full max-w-[460px] overflow-hidden"
    >
      {/* Inner static label */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="flex flex-col items-center gap-1 text-center">
          <span
            className="display-xl text-[color:var(--ink)] !leading-none [font-weight:700]"
            style={{ fontSize: "clamp(28px, 9vw, 42px)" }}
          >
            {seasonYear}
          </span>
          <span className="caption-uppercase tracking-[0.30em] text-[color:var(--muted)]">
            The Grid
          </span>
          <span
            className="inline-block w-12 h-px mt-2"
            style={{ background: "var(--accent)" }}
          />
        </div>
      </div>

      {/* Inner ring */}
      {innerRing.map((team, i) => {
        const c = colorFor(team);
        return (
          <OrbitingCircles
            key={team.team}
            radius={innerR}
            duration={28}
            delay={(i / Math.max(innerRing.length, 1)) * 28}
            pathColor="rgba(255,255,255,0.06)"
          >
            <span
              data-team={team.team}
              className="flex items-center justify-center w-12 h-12 rounded-full border text-[11px] font-mono uppercase tracking-[0.10em] text-[color:var(--ink)]"
              style={{
                borderColor: c,
                background: "var(--surface-card)",
                boxShadow: `0 0 12px ${c}40`,
              }}
              title={team.team}
            >
              {teamInitials(team.team)}
            </span>
          </OrbitingCircles>
        );
      })}

      {/* Outer ring (reverse direction so it doesn't read as repeating) */}
      {outerRing.map((team, i) => {
        const c = colorFor(team);
        return (
          <OrbitingCircles
            key={team.team}
            radius={outerR}
            duration={36}
            delay={(i / Math.max(outerRing.length, 1)) * 36}
            reverse
            pathColor="rgba(255,255,255,0.04)"
          >
            <span
              data-team={team.team}
              className="flex items-center justify-center w-12 h-12 rounded-full border text-[11px] font-mono uppercase tracking-[0.10em] text-[color:var(--ink)]"
              style={{
                borderColor: c,
                background: "var(--surface-card)",
                boxShadow: `0 0 12px ${c}40`,
              }}
              title={team.team}
            >
              {teamInitials(team.team)}
            </span>
          </OrbitingCircles>
        );
      })}
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
