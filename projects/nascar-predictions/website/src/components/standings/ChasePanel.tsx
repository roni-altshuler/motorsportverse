"use client";

/**
 * The Chase panel — NASCAR's sanctioned divergence from the shared standings
 * template. Three surfaces, all fed by playoff_projection.json (per-driver
 * ladder: p_make_playoffs → p_title):
 *
 *   1. Playoff cut line — the top-16 regular-season picture as it stands
 *      today (points + wins), with the cut drawn after P16 and the bubble
 *      (a few spots either side of the line) highlighted.
 *   2. Playoff ladder — per-driver P(make playoffs) and P(title) bars.
 *   3. Title-odds strip — the championship favourites at a glance.
 *
 * The whole section is GATED: the server page only passes `projection` when
 * historical_backtest/playoffs.json reports gate.pass === true (the playoff
 * simulator must beat its historical honesty bar before title odds ship).
 */
import { motion } from "framer-motion";

import DriverPortrait from "@/components/standings/DriverPortrait";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { makeColor, teamColor as teamColorFor } from "@/lib/teams";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { PlayoffDriver, PlayoffProjection } from "@/types/nascar";

const BUBBLE_SPREAD = 3; // rows either side of the cut counted as "the bubble"
const CUTLINE_ROWS_BELOW = 6; // how far below the cut the table keeps going
const LADDER_ROWS = 20;

function pct(p: number, digits = 0): string {
  if (p >= 0.999) return "100%";
  if (p > 0 && p < 0.001) return "<0.1%";
  return `${(p * 100).toFixed(digits)}%`;
}

export default function ChasePanel({ projection }: { projection: PlayoffProjection }) {
  const reduced = useReducedMotion();
  const fieldSize = projection.format.playoffFieldSize;
  // Regular-season order as it stands today: points, wins as the tiebreak.
  const byPoints: PlayoffDriver[] = [...projection.drivers].sort(
    (a, b) => b.points - a.points || b.wins - a.wins,
  );
  const cutRows = byPoints.slice(0, fieldSize + CUTLINE_ROWS_BELOW);
  const ladder = [...projection.drivers]
    .sort((a, b) => b.pMakePlayoffs - a.pMakePlayoffs || b.pTitle - a.pTitle)
    .slice(0, LADDER_ROWS);
  const titleFavs = [...projection.drivers]
    .sort((a, b) => b.pTitle - a.pTitle)
    .filter((d) => d.pTitle > 0)
    .slice(0, 8);
  const maxTitle = titleFavs[0]?.pTitle ?? 1;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="display-md mb-2">The Chase — Playoff Projection</h2>
        <p className="body-md text-[color:var(--text-muted)] max-w-2xl">
          {projection.format.regularSeasonRaces} regular-season races set a{" "}
          {fieldSize}-driver playoff field, then {projection.format.playoffRaces} playoff
          races decide the title. {projection.regularSeasonRacesRemaining} regular-season
          race{projection.regularSeasonRacesRemaining === 1 ? "" : "s"} remain before the
          field locks.
        </p>
      </div>

      {/* ── 1. Playoff cut line ─────────────────────────────────────────── */}
      <div className="card overflow-hidden">
        <div className="flex items-baseline justify-between px-5 pt-5 pb-3">
          <h3 className="section-heading !mb-0">Playoff Cut Line</h3>
          <p className="text-[11px] font-mono uppercase tracking-[0.14em] text-[color:var(--text-muted)]">
            points + wins · today
          </p>
        </div>
        <ol>
          {cutRows.map((d, i) => {
            const pos = i + 1;
            const inField = pos <= fieldSize;
            const onBubble =
              pos > fieldSize - BUBBLE_SPREAD && pos <= fieldSize + BUBBLE_SPREAD;
            const color = teamColorFor(d.team);
            return (
              <li key={d.code}>
                <div
                  className="flex items-center gap-3 border-t border-[var(--hairline)] px-5 py-2"
                  style={{
                    background: onBubble
                      ? "color-mix(in srgb, var(--accent) 7%, transparent)"
                      : undefined,
                    opacity: inField || onBubble ? 1 : 0.55,
                  }}
                >
                  <span
                    className="w-7 shrink-0 text-center font-mono text-sm font-bold tabular-nums"
                    style={{ color: inField ? "var(--ink)" : "var(--muted)" }}
                  >
                    {pos}
                  </span>
                  <DriverPortrait
                    driver={d.code}
                    driverFullName={d.name}
                    team={d.team}
                    teamColor={color}
                    headshotUrl={null}
                    size={28}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-[var(--ink)]">
                      {d.name}
                      {onBubble && (
                        <span
                          className="ml-2 rounded-full px-1.5 py-px font-mono text-[9px] uppercase tracking-[0.12em]"
                          style={{
                            color: "var(--accent-ink)",
                            background: "var(--accent)",
                          }}
                        >
                          Bubble
                        </span>
                      )}
                    </p>
                    <p className="truncate text-[11px] text-[color:var(--text-muted)]">
                      {d.team}
                      {d.make ? ` · ${d.make}` : ""}
                    </p>
                  </div>
                  {d.wins > 0 && (
                    <span
                      className="shrink-0 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em]"
                      style={{
                        color: "var(--accent-podium-1)",
                        borderColor:
                          "color-mix(in srgb, var(--accent-podium-1) 45%, transparent)",
                      }}
                    >
                      {d.wins} win{d.wins === 1 ? "" : "s"}
                    </span>
                  )}
                  <span className="w-16 shrink-0 text-right font-mono text-sm tabular-nums text-[var(--ink)]">
                    <NumberTicker value={Math.round(d.points)} />
                  </span>
                  <span
                    className="hidden w-16 shrink-0 text-right font-mono text-xs tabular-nums sm:inline"
                    style={{
                      color:
                        d.pMakePlayoffs >= 0.5 ? "var(--success)" : "var(--text-muted)",
                    }}
                    title="Probability of making the playoff field"
                  >
                    {pct(d.pMakePlayoffs)}
                  </span>
                </div>
                {pos === fieldSize && (
                  <div
                    className="flex items-center gap-3 px-5 py-1.5"
                    style={{ background: "var(--accent)" }}
                    role="separator"
                    aria-label={`Playoff cut line — top ${fieldSize} make the Chase`}
                  >
                    <span
                      className="font-mono text-[10px] font-bold uppercase tracking-[0.22em]"
                      style={{ color: "var(--accent-ink)" }}
                    >
                      Playoff cut — top {fieldSize} make the Chase
                    </span>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
        <p className="px-5 py-3 text-[11px] text-[color:var(--text-muted)]">
          Right-hand column: modelled probability of making the {fieldSize}-driver field.
          Race winners are effectively safe — a win is the strongest playoff currency.
        </p>
      </div>

      {/* ── 2 + 3. Playoff ladder + title odds ─────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="card p-5">
          <h3 className="section-heading">Playoff Ladder</h3>
          <p className="mb-4 text-[11px] text-[color:var(--text-muted)]">
            Per driver: make the {fieldSize}-car field → win the title. Simulated over the
            remaining regular season and the full {projection.format.playoffRaces}-race Chase.
          </p>
          <ol className="space-y-2.5">
            {ladder.map((d) => {
              const color = teamColorFor(d.team);
              return (
                <li key={d.code} className="flex items-center gap-3">
                  <DriverPortrait
                    driver={d.code}
                    driverFullName={d.name}
                    team={d.team}
                    teamColor={color}
                    headshotUrl={null}
                    size={26}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-baseline justify-between gap-2">
                      <span className="truncate text-xs font-medium text-[var(--ink)]">
                        {d.name}
                      </span>
                      <span className="shrink-0 font-mono text-[10px] tabular-nums text-[color:var(--text-muted)]">
                        {pct(d.pMakePlayoffs)} in · {pct(d.pTitle, d.pTitle >= 0.1 ? 0 : 1)}{" "}
                        title
                      </span>
                    </div>
                    <div className="flex h-1.5 gap-1">
                      <span className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--surface-2)]">
                        <motion.span
                          className="absolute inset-y-0 left-0 rounded-full"
                          style={{ background: color }}
                          initial={reduced ? false : { width: 0 }}
                          animate={{ width: `${d.pMakePlayoffs * 100}%` }}
                          transition={{ duration: 0.5 }}
                        />
                      </span>
                      <span className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--surface-2)]">
                        <motion.span
                          className="absolute inset-y-0 left-0 rounded-full"
                          style={{ background: "var(--accent)" }}
                          initial={reduced ? false : { width: 0 }}
                          animate={{ width: `${d.pTitle * 100}%` }}
                          transition={{ duration: 0.5, delay: 0.1 }}
                        />
                      </span>
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
          <div className="mt-3 flex items-center gap-4 text-[10px] font-mono uppercase tracking-[0.12em] text-[color:var(--text-muted)]">
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-1.5 w-4 rounded-full bg-[var(--muted)]" />
              make playoffs
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-1.5 w-4 rounded-full"
                style={{ background: "var(--accent)" }}
              />
              win title
            </span>
          </div>
        </div>

        <div className="card p-5">
          <h3 className="section-heading">Title Odds</h3>
          <p className="mb-4 text-[11px] text-[color:var(--text-muted)]">
            Probability of lifting the Cup at Homestead, through the full Chase format.
          </p>
          <ol className="space-y-3">
            {titleFavs.map((d) => {
              const color = teamColorFor(d.team);
              return (
                <li key={d.code} className="flex items-center gap-3">
                  <DriverPortrait
                    driver={d.code}
                    driverFullName={d.name}
                    team={d.team}
                    teamColor={color}
                    headshotUrl={null}
                    size={32}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-baseline justify-between gap-2">
                      <span className="truncate text-sm font-medium text-[var(--ink)]">
                        {d.name}
                        {d.make && (
                          <span
                            className="ml-2 align-middle font-mono text-[9px] uppercase tracking-[0.14em]"
                            style={{ color: makeColor(d.make) }}
                          >
                            {d.make}
                          </span>
                        )}
                      </span>
                      <span className="shrink-0 font-mono text-sm font-bold tabular-nums text-[var(--ink)]">
                        {pct(d.pTitle, d.pTitle >= 0.1 ? 1 : 2)}
                      </span>
                    </div>
                    <div className="relative h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
                      <motion.span
                        className="absolute inset-y-0 left-0 rounded-full"
                        style={{
                          background: "var(--accent)",
                          boxShadow:
                            "0 0 8px color-mix(in srgb, var(--accent) 55%, transparent)",
                        }}
                        initial={reduced ? false : { width: 0 }}
                        animate={{ width: `${(d.pTitle / maxTitle) * 100}%` }}
                        transition={{ duration: 0.5 }}
                      />
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
          <p className="mt-4 text-[10px] text-[color:var(--text-muted)]">
            Playoff odds ship only because the simulator beat its historical bar across
            2017–2025 replays — the honesty gate is checked at build time.
          </p>
        </div>
      </div>
    </div>
  );
}
