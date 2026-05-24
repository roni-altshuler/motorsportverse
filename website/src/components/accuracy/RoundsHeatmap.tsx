"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";

import { NumberTicker } from "@/components/magicui/number-ticker";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { SeasonData, SeasonTrackerRound } from "@/types";

interface RoundsHeatmapProps {
  rounds: SeasonTrackerRound[];
  season: SeasonData | null;
}

/**
 * Grid heatmap of per-round prediction accuracy.  One cell per scheduled
 * round; colour-encoded by accuracy band.  Click opens a modal showing the
 * race name, accuracy, mean error, and a link to the race detail page.
 *
 * Empty / not-yet-evaluated rounds render as a hairline placeholder.
 */
export default function RoundsHeatmap({ rounds, season }: RoundsHeatmapProps) {
  const reduced = useReducedMotion();
  const [openRound, setOpenRound] = useState<number | null>(null);

  const totalRounds = season?.totalRounds ?? rounds.length;

  // Build a lookup keyed by round number so empty slots render as placeholders.
  const byRound = useMemo(() => {
    const map = new Map<number, SeasonTrackerRound>();
    for (const r of rounds) map.set(r.round, r);
    return map;
  }, [rounds]);

  const getRoundName = (round: number) => {
    if (!season) return `Round ${round}`;
    const race = season.calendar.find((c) => c.round === round);
    return race ? race.name : `Round ${round}`;
  };

  // Map accuracy → colour token. ≥80% success-green, 50–79% warning-amber,
  // <50% slips into f1-red as a semantic miss signal (red here flags a poor
  // prediction outcome — kept off mid-range cells so it doesn't read as
  // decorative).
  const colourFor = (pct: number | null | undefined): string => {
    if (pct == null) return "var(--surface-card)";
    if (pct >= 80) return "var(--success)";
    if (pct >= 65)
      return "color-mix(in srgb, var(--success) 70%, var(--warning))";
    if (pct >= 50) return "var(--warning)";
    if (pct >= 35)
      return "color-mix(in srgb, var(--warning) 50%, var(--accent-f1-red))";
    return "var(--accent-f1-red)";
  };

  const cells = useMemo(() => {
    const list: Array<{
      round: number;
      entry: SeasonTrackerRound | null;
    }> = [];
    for (let i = 1; i <= totalRounds; i++) {
      list.push({ round: i, entry: byRound.get(i) ?? null });
    }
    return list;
  }, [totalRounds, byRound]);

  const activeRound =
    openRound != null ? byRound.get(openRound) ?? null : null;

  return (
    <>
      <div
        className="grid gap-2 sm:gap-3"
        style={{
          gridTemplateColumns: "repeat(auto-fit, minmax(72px, 1fr))",
        }}
      >
        {cells.map(({ round, entry }) => {
          const hasData =
            entry != null && entry.hasActual && entry.accuracyPct != null;
          const pct = entry?.accuracyPct ?? null;
          const colour = colourFor(pct);
          const isMiss = pct != null && pct < 50;

          const baseStyle: React.CSSProperties = hasData
            ? {
                background: `color-mix(in srgb, ${colour} 22%, var(--surface-card))`,
                borderColor: `color-mix(in srgb, ${colour} 55%, transparent)`,
              }
            : {
                background: "var(--surface-card)",
                borderColor: "var(--border)",
              };

          return (
            <motion.button
              key={round}
              type="button"
              disabled={!hasData}
              onClick={() => hasData && setOpenRound(round)}
              className="relative aspect-square rounded-xl border text-left p-2 flex flex-col justify-between focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent-live)]"
              style={baseStyle}
              whileHover={
                reduced || !hasData
                  ? undefined
                  : {
                      y: -3,
                      boxShadow: `0 6px 20px color-mix(in srgb, ${colour} 35%, transparent)`,
                    }
              }
              transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
              aria-label={
                hasData
                  ? `${getRoundName(round)} — ${pct}% accuracy`
                  : `${getRoundName(round)} — not yet evaluated`
              }
            >
              <span
                className="text-[10px] font-display font-bold uppercase tracking-[0.14em]"
                style={{ color: "var(--text-muted)" }}
              >
                R{round}
              </span>
              {hasData ? (
                <span
                  className="font-mono font-tabular font-black text-xl sm:text-2xl leading-none text-center w-full"
                  style={{
                    color: isMiss
                      ? "var(--accent-f1-red)"
                      : "var(--text)",
                  }}
                >
                  <NumberTicker value={pct ?? 0} decimalPlaces={0} />
                  <span className="text-xs ml-0.5">%</span>
                </span>
              ) : (
                <span
                  className="text-[10px] font-mono uppercase tracking-[0.1em] text-center w-full"
                  style={{ color: "var(--text-muted)" }}
                >
                  —
                </span>
              )}
            </motion.button>
          );
        })}
      </div>

      {/* ━━━ Detail modal ━━━ */}
      <AnimatePresence>
        {openRound != null && activeRound && (
          <motion.div
            key="heatmap-modal-backdrop"
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={() => setOpenRound(null)}
            aria-modal="true"
            role="dialog"
          >
            <div
              className="absolute inset-0"
              style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(6px)" }}
              aria-hidden
            />
            <motion.div
              className="relative card p-6 sm:p-8 max-w-md w-full"
              initial={reduced ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.96 }}
              animate={reduced ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1 }}
              exit={reduced ? { opacity: 0 } : { opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              onClick={(e) => e.stopPropagation()}
            >
              <button
                type="button"
                onClick={() => setOpenRound(null)}
                className="absolute top-3 right-3 w-8 h-8 rounded-full flex items-center justify-center text-[color:var(--text-muted)] hover:text-[color:var(--text)] hover:bg-[color:var(--bg-card-hover)] transition-colors"
                aria-label="Close round details"
              >
                ×
              </button>
              <p
                className="eyebrow mb-2"
                style={{ color: "var(--text-muted)" }}
              >
                Round {activeRound.round}
              </p>
              <h3
                className="font-display font-bold text-xl mb-5 tracking-tight"
                style={{ color: "var(--text)" }}
              >
                {getRoundName(activeRound.round)}
              </h3>
              <div className="grid grid-cols-2 gap-3 mb-5">
                <div className="metric-card text-center">
                  <p className="eyebrow mb-1">Accuracy</p>
                  <p
                    className="font-mono font-tabular font-black text-3xl"
                    style={{
                      color: colourFor(activeRound.accuracyPct),
                    }}
                  >
                    {activeRound.accuracyPct != null ? (
                      <>
                        <NumberTicker
                          value={activeRound.accuracyPct}
                          decimalPlaces={0}
                        />
                        <span className="text-base ml-0.5">%</span>
                      </>
                    ) : (
                      <span className="text-base">—</span>
                    )}
                  </p>
                </div>
                <div className="metric-card text-center">
                  <p className="eyebrow mb-1">Mean Error</p>
                  <p
                    className="font-mono font-tabular font-black text-3xl"
                    style={{ color: "var(--text)" }}
                  >
                    {activeRound.meanError != null ? (
                      <NumberTicker
                        value={activeRound.meanError}
                        decimalPlaces={1}
                      />
                    ) : (
                      "—"
                    )}
                    <span className="text-xs ml-1 text-[color:var(--text-muted)]">
                      pos
                    </span>
                  </p>
                </div>
              </div>
              {(activeRound.exactMatches != null || activeRound.within3 != null) && (
                <div
                  className="flex justify-between text-xs mb-5"
                  style={{ color: "var(--text-muted)" }}
                >
                  <span>
                    Exact matches:{" "}
                    <span style={{ color: "var(--text)" }}>
                      {activeRound.exactMatches ?? "—"}
                    </span>
                  </span>
                  <span>
                    Within 3:{" "}
                    <span style={{ color: "var(--text)" }}>
                      {activeRound.within3 ?? "—"}
                    </span>
                  </span>
                </div>
              )}
              <Link
                href={`/race/${activeRound.round}`}
                className="inline-flex items-center gap-2 text-sm font-semibold text-[color:var(--accent-live)] hover:text-[color:var(--accent-live-hover)] transition-colors"
                onClick={() => setOpenRound(null)}
              >
                Open race detail →
              </Link>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
