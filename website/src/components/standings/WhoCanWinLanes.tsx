"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { motion } from "framer-motion";

import DriverPortrait from "@/components/standings/DriverPortrait";
import { AnimatedBeam } from "@/components/magicui/animated-beam";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { StandingsData, SeasonData } from "@/types";

interface WhoCanWinLanesProps {
  standings: StandingsData;
  season: SeasonData | null;
}

/**
 * "Race to the flag" lanes — one horizontal lane per championship contender.
 * Each lane shows current points (solid team color) and the maximum possible
 * additional points (ghost team color) the driver could still earn.
 *
 * Drivers whose theoretical maximum is still less than the current leader's
 * points are mathematically eliminated; they appear dimmed and have no beam
 * drawn to the CHAMPION ZONE anchor on the right.
 *
 * Upper bound per remaining round = 25 (win) + 1 (fastest lap) + 8 (sprint),
 * applied uniformly. Conservative on weekends without sprints — favours the
 * contender, which is the safe direction for "can still win" math.
 */

const MAX_POINTS_PER_ROUND = 25 + 1 + 8; // win + fastest lap + sprint

export default function WhoCanWinLanes({ standings, season }: WhoCanWinLanesProps) {
  const reduced = useReducedMotion();

  const completedRounds = season?.completedRounds?.length ?? standings.lastUpdatedRound ?? 0;
  const totalRounds = season?.totalRounds ?? 22;
  const remainingRounds = Math.max(totalRounds - completedRounds, 0);
  const remainingPointsCap = remainingRounds * MAX_POINTS_PER_ROUND;

  const leaderPoints = standings.drivers[0]?.points ?? 0;

  // Compute lane data: sort by max possible (desc) so the strongest title
  // pictures sit at the top.  Re-derive `canStillWin` locally with the same
  // rule the design spec calls out: max possible < leader's CURRENT points.
  const lanes = useMemo(() => {
    const headshotByCode = new Map(
      standings.drivers.map((d) => [d.driver, d.headshotUrl ?? null]),
    );
    return standings.wdcPossibility
      .map((w) => {
        const maxPossible = w.currentPoints + remainingPointsCap;
        const eliminated = maxPossible < leaderPoints;
        return {
          driver: w.driver,
          driverFullName: w.driverFullName,
          team: w.team,
          teamColor: w.teamColor,
          currentPoints: w.currentPoints,
          maxPossible,
          eliminated,
          headshotUrl: headshotByCode.get(w.driver) ?? null,
        };
      })
      .sort((a, b) => b.maxPossible - a.maxPossible);
  }, [standings.drivers, standings.wdcPossibility, remainingPointsCap, leaderPoints]);

  // The horizontal axis is shared across lanes — fill widths are proportional
  // to the highest "max possible" across all contenders so the bars line up.
  const axisMax = Math.max(
    ...lanes.map((l) => l.maxPossible),
    leaderPoints,
    1,
  );

  // Refs for beam endpoints. The beam connects each lane-end to the anchor.
  //
  // React 19's `react-hooks/refs` rule forbids touching a ref's `.current`
  // during render — so we use a callback-ref pattern. Each lane attaches a
  // `setLaneEl(driver)` callback to its end-of-bar div; that callback writes
  // the DOM node into state. We then wrap each node in a synthetic
  // `RefObject` shape that AnimatedBeam expects (it only reads `.current`).
  const containerRef = useRef<HTMLDivElement>(null);
  const anchorRef = useRef<HTMLDivElement>(null);
  const [laneNodes, setLaneNodes] = useState<Map<string, HTMLDivElement | null>>(
    () => new Map(),
  );

  const setLaneEl = useCallback(
    (driver: string) => (el: HTMLDivElement | null) => {
      setLaneNodes((prev) => {
        if (prev.get(driver) === el) return prev;
        const next = new Map(prev);
        if (el === null) next.delete(driver);
        else next.set(driver, el);
        return next;
      });
    },
    [],
  );

  const getLaneRef = (driver: string): RefObject<HTMLDivElement | null> => ({
    get current() {
      return laneNodes.get(driver) ?? null;
    },
    set current(_v: HTMLDivElement | null) {
      /* read-only synthetic ref — writes are ignored */
    },
  });

  // After mount, force a layout pass so AnimatedBeam can read bounding boxes.
  // (AnimatedBeam already does its own ResizeObserver — this just nudges it
  // once after the first paint so refs are populated.)
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const contenders = lanes.filter((l) => !l.eliminated);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="display-md mb-2">Mathematical Title Picture</h2>
        <p className="body-md text-[color:var(--text-muted)] max-w-2xl">
          Drivers who could still win the championship if results break their way.
          Bars show current points (solid) plus the maximum additional points
          available across the remaining {remainingRounds} round
          {remainingRounds === 1 ? "" : "s"}.
        </p>
      </div>

      <div
        ref={containerRef}
        className="relative card p-6 sm:p-8 overflow-hidden"
      >
        {/* Lanes column + champion-zone column */}
        <div className="grid grid-cols-[1fr_auto] gap-6 sm:gap-10 items-stretch">
          {/* ━━━ Lanes ━━━ */}
          <ol className="space-y-3 sm:space-y-4">
            {lanes.map((lane) => {
              const currentPct = (lane.currentPoints / axisMax) * 100;
              const maxPct = (lane.maxPossible / axisMax) * 100;
              return (
                <li
                  key={lane.driver}
                  data-team={lane.team}
                  className="flex items-center gap-3 sm:gap-4"
                  style={{
                    opacity: lane.eliminated ? 0.4 : 1,
                    transition: reduced ? undefined : "opacity 240ms ease-out",
                  }}
                >
                  <DriverPortrait
                    driver={lane.driver}
                    driverFullName={lane.driverFullName}
                    team={lane.team}
                    teamColor={lane.teamColor}
                    headshotUrl={lane.headshotUrl}
                    size={40}
                  />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline justify-between mb-1 gap-3">
                      <span
                        className="font-display font-bold tracking-[0.04em] uppercase text-sm sm:text-base truncate"
                        style={{ color: "var(--text)" }}
                      >
                        {lane.driver}
                        <span
                          className="ml-2 font-sans font-normal normal-case text-[10px] sm:text-xs tracking-normal"
                          style={{ color: "var(--text-muted)" }}
                        >
                          {lane.team}
                        </span>
                      </span>
                      <span
                        className="text-xs uppercase tracking-[0.12em]"
                        style={{
                          color: lane.eliminated
                            ? "var(--text-muted)"
                            : "var(--success)",
                        }}
                      >
                        {lane.eliminated ? "Eliminated" : "In contention"}
                      </span>
                    </div>

                    {/* Bar track */}
                    <div
                      className="relative h-3 rounded-full overflow-hidden"
                      style={{
                        background: "var(--surface-card)",
                        border: "1px solid var(--border)",
                      }}
                    >
                      {/* Ghost fill — max possible additional points */}
                      <motion.div
                        className="absolute inset-y-0 left-0"
                        style={{
                          background: `color-mix(in srgb, ${lane.teamColor} 28%, transparent)`,
                          width: `${maxPct}%`,
                        }}
                        initial={reduced ? false : { width: 0 }}
                        animate={{ width: `${maxPct}%` }}
                        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                      />
                      {/* Solid fill — current points */}
                      <motion.div
                        className="absolute inset-y-0 left-0"
                        style={{
                          background: lane.teamColor,
                          width: `${currentPct}%`,
                          boxShadow: lane.eliminated
                            ? undefined
                            : `0 0 12px color-mix(in srgb, ${lane.teamColor} 60%, transparent)`,
                        }}
                        initial={reduced ? false : { width: 0 }}
                        animate={{ width: `${currentPct}%` }}
                        transition={{
                          duration: 0.6,
                          delay: 0.05,
                          ease: [0.16, 1, 0.3, 1],
                        }}
                      />

                      {/* Lane-end anchor (invisible) — beam origin */}
                      <div
                        ref={setLaneEl(lane.driver)}
                        className="absolute top-1/2"
                        style={{
                          left: `${maxPct}%`,
                          transform: "translate(-50%, -50%)",
                          width: 1,
                          height: 1,
                        }}
                        aria-hidden
                      />
                    </div>

                    {/* Numbers row */}
                    <div className="flex items-center justify-between mt-1.5 text-[11px] font-mono font-tabular">
                      <span style={{ color: "var(--text-muted)" }}>
                        <NumberTicker value={lane.currentPoints} />{" "}
                        <span className="uppercase tracking-[0.1em]">pts now</span>
                      </span>
                      <span
                        style={{
                          color: lane.eliminated
                            ? "var(--text-muted)"
                            : "var(--text)",
                        }}
                      >
                        max{" "}
                        <span className="font-bold">
                          <NumberTicker value={lane.maxPossible} />
                        </span>
                      </span>
                    </div>
                  </div>

                  {/* Trailing max-total chip — also doubles as the visual end-cap */}
                  <div
                    className="hidden sm:flex flex-col items-end shrink-0 w-14 text-right"
                    style={{
                      color: lane.eliminated
                        ? "var(--text-muted)"
                        : "var(--text)",
                    }}
                  >
                    <span className="text-[10px] uppercase tracking-[0.12em] text-[color:var(--text-muted)]">
                      Max
                    </span>
                    <span className="font-mono font-tabular font-black text-lg leading-none">
                      <NumberTicker value={lane.maxPossible} />
                    </span>
                  </div>
                </li>
              );
            })}
          </ol>

          {/* ━━━ CHAMPION ZONE anchor ━━━ */}
          <div className="flex items-center">
            <div
              ref={anchorRef}
              className="relative flex flex-col items-center justify-center px-4 sm:px-5 py-6 sm:py-8 rounded-2xl text-center"
              style={{
                background:
                  "linear-gradient(180deg, color-mix(in srgb, var(--success) 18%, transparent), color-mix(in srgb, var(--success) 4%, transparent))",
                border: "1px solid color-mix(in srgb, var(--success) 40%, transparent)",
                boxShadow:
                  "0 0 28px color-mix(in srgb, var(--success) 25%, transparent)",
                minHeight: 120,
                minWidth: 110,
              }}
            >
              <span
                className="text-[10px] sm:text-xs font-display font-bold uppercase tracking-[0.18em]"
                style={{ color: "var(--success)" }}
              >
                Champion
              </span>
              <span
                className="text-[10px] sm:text-xs font-display font-bold uppercase tracking-[0.18em] mb-2"
                style={{ color: "var(--success)" }}
              >
                Zone
              </span>
              <span
                className="font-mono font-tabular font-black text-2xl sm:text-3xl leading-none"
                style={{ color: "var(--text)" }}
              >
                <NumberTicker value={leaderPoints} />
              </span>
              <span
                className="text-[10px] uppercase tracking-[0.12em] mt-1"
                style={{ color: "var(--text-muted)" }}
              >
                Leader pts
              </span>
            </div>
          </div>
        </div>

        {/* Beams from each in-contention lane to the champion-zone anchor.
            Skipped entirely under reduced motion to honour the global rule. */}
        {mounted && !reduced &&
          contenders.map((lane, i) => (
            <AnimatedBeam
              key={`beam-${lane.driver}`}
              containerRef={containerRef}
              fromRef={getLaneRef(lane.driver)}
              toRef={anchorRef}
              curvature={20}
              duration={4.5}
              delay={i * 0.18}
              pathColor="rgba(255,255,255,0.05)"
              pathWidth={1.5}
              gradientStartColor={lane.teamColor}
              gradientStopColor="var(--success)"
            />
          ))}
      </div>

      <p className="text-xs text-[color:var(--text-muted)]">
        Eliminated when a driver{"'"}s maximum reachable total is less than the
        current leader{"'"}s points. Max per round assumes win + fastest lap +
        sprint victory ({MAX_POINTS_PER_ROUND} pts).
      </p>
    </div>
  );
}
