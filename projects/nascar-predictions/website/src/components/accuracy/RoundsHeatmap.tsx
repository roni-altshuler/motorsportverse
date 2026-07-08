"use client";

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { useMemo, useState } from "react";

import { NumberTicker } from "@/components/magicui/number-ticker";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { ForwardEvalRound, RaceAccuracy } from "@/types/nascar";

/**
 * Grid heatmap of per-round prediction accuracy (NASCAR port of the RaceIQ
 * F1 flagship's RoundsHeatmap). One cell per scheduled round, colour-encoded by
 * a podium-weighted accuracy band derived from the round's race. Click opens a
 * modal with the round breakdown and a link to the race detail page. Empty /
 * not-yet-scored rounds render as a hairline placeholder.
 *
 * FE has no single per-round "accuracyPct" like F1's season tracker, so the
 * score is derived honestly from the race's RaceAccuracy:
 *   0.6·(podium hits / 3) + 0.4·(within-5 order rate), re-normalised when a
 * component is missing — never fabricated.
 */

export function raceAccuracyPct(a: RaceAccuracy | undefined): number | null {
  if (!a || !a.n) return null;
  const podium = a.podium_hits != null ? a.podium_hits / 3 : null;
  const order =
    a.within_5 != null ? a.within_5 / a.n : a.within_3 != null ? a.within_3 / a.n : null;
  if (podium == null && order == null) {
    return a.winner_hit != null ? (a.winner_hit ? 100 : 0) : null;
  }
  const weight = (podium != null ? 0.6 : 0) + (order != null ? 0.4 : 0);
  const raw = (podium != null ? 0.6 * podium : 0) + (order != null ? 0.4 * order : 0);
  return Math.round((raw / weight) * 100);
}

interface RoundsHeatmapProps {
  rounds: ForwardEvalRound[];
  totalRounds: number;
}

// Accuracy → colour band. ≥80 success-green, mid amber, <50 slips to penalty
// red as a semantic "miss" signal (red is semantic here, not a brand colour).
function colourFor(pct: number | null | undefined): string {
  if (pct == null) return "var(--surface-card)";
  if (pct >= 80) return "var(--success)";
  if (pct >= 65) return "color-mix(in srgb, var(--success) 70%, var(--warning))";
  if (pct >= 50) return "var(--warning)";
  if (pct >= 35) return "color-mix(in srgb, var(--warning) 50%, var(--accent-negative))";
  return "var(--accent-negative)";
}

export default function RoundsHeatmap({ rounds, totalRounds }: RoundsHeatmapProps) {
  const reduced = useReducedMotion();
  const [openRound, setOpenRound] = useState<number | null>(null);

  const byRound = useMemo(() => {
    const map = new Map<number, ForwardEvalRound>();
    for (const r of rounds) map.set(r.round, r);
    return map;
  }, [rounds]);

  const total = totalRounds || rounds.length;
  const nameFor = (round: number) => byRound.get(round)?.venueName ?? `Round ${round}`;

  const cells = useMemo(
    () => Array.from({ length: total }, (_, i) => i + 1).map((round) => ({ round })),
    [total],
  );

  const active = openRound != null ? byRound.get(openRound) ?? null : null;
  const activePct = active ? raceAccuracyPct(active.race) : null;

  return (
    <>
      <div
        className="grid gap-2 sm:gap-3"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(72px, 1fr))" }}
      >
        {cells.map(({ round }) => {
          const entry = byRound.get(round) ?? null;
          const pct = raceAccuracyPct(entry?.race);
          const hasData = pct != null;
          const colour = colourFor(pct);
          const isMiss = pct != null && pct < 50;

          const baseStyle: React.CSSProperties = hasData
            ? {
                background: `color-mix(in srgb, ${colour} 22%, var(--surface-card))`,
                borderColor: `color-mix(in srgb, ${colour} 55%, transparent)`,
              }
            : { background: "var(--surface-card)", borderColor: "var(--border)" };

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
                  ? `${nameFor(round)} — ${pct}% accuracy`
                  : `Round ${round} — not yet scored`
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
                  style={{ color: isMiss ? "var(--accent-negative)" : "var(--text)" }}
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
        {openRound != null && active && (
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
                className="absolute top-3 right-3 w-8 h-8 rounded-full flex items-center justify-center text-[color:var(--text-muted)] hover:text-[color:var(--text)] transition-colors"
                aria-label="Close round details"
              >
                ×
              </button>
              <p className="eyebrow mb-2" style={{ color: "var(--text-muted)" }}>
                Round {active.round}
              </p>
              <h3
                className="font-display font-bold text-xl mb-5 tracking-tight"
                style={{ color: "var(--text)" }}
              >
                {nameFor(active.round)}
              </h3>
              <div className="grid grid-cols-2 gap-3 mb-5">
                <div className="metric-card text-center">
                  <p className="eyebrow mb-1">Accuracy</p>
                  <p
                    className="font-mono font-tabular font-black text-3xl"
                    style={{ color: colourFor(activePct) }}
                  >
                    {activePct != null ? (
                      <>
                        <NumberTicker value={activePct} decimalPlaces={0} />
                        <span className="text-base ml-0.5">%</span>
                      </>
                    ) : (
                      <span className="text-base">—</span>
                    )}
                  </p>
                </div>
                <div className="metric-card text-center">
                  <p className="eyebrow mb-1">Mean Error</p>
                  <p className="font-mono font-tabular font-black text-3xl" style={{ color: "var(--text)" }}>
                    {active.race.mean_position_error != null ? (
                      <NumberTicker value={active.race.mean_position_error} decimalPlaces={1} />
                    ) : (
                      "—"
                    )}
                    <span className="text-xs ml-1 text-[color:var(--text-muted)]">pos</span>
                  </p>
                </div>
              </div>
              <div className="flex justify-between text-xs mb-5" style={{ color: "var(--text-muted)" }}>
                <span>
                  Winner:{" "}
                  <span style={{ color: "var(--text)" }}>
                    {active.race.winner_hit == null ? "—" : active.race.winner_hit ? "✓ hit" : "miss"}
                  </span>
                </span>
                <span>
                  Podium hits:{" "}
                  <span style={{ color: "var(--text)" }}>{active.race.podium_hits ?? "—"}/3</span>
                </span>
              </div>
              <Link
                href={`/race/${active.round}`}
                className="inline-flex items-center gap-2 text-sm font-semibold text-[color:var(--accent)] hover:underline"
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
