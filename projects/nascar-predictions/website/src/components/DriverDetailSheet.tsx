"use client";

/**
 * Driver detail sheet (Formula E pop-out).
 *
 * A modal that opens when a classification table row is clicked. It shows the
 * driver's per-race forecast markets (win / podium / top-6 / top-10), their
 * projected mean finish + finish range, and — when a season standings record
 * is available — a season form sparkline seeded from `pointsHistory`.
 *
 * Interaction contract:
 *   - opens for the clicked driver
 *   - closes on overlay click, Escape, or the close button
 *   - focus is moved into the dialog on open and returned on close
 *   - respects prefers-reduced-motion (no entrance animation)
 *
 * This is a client component fed entirely by props — it never imports the
 * fs-based loader.
 */
import { useEffect, useMemo, useRef } from "react";
import { motion } from "framer-motion";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

import DriverPortrait from "@/components/standings/DriverPortrait";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { ClassificationEntry, DriverStanding } from "@/types/nascar";

interface Props {
  /** The classification entry for the clicked driver (active race tab). */
  entry: ClassificationEntry | null;
  /** Season standings, used to seed the form sparkline + season stats. */
  driverStandings: DriverStanding[];
  /** Which race the markets belong to — surfaces in the header. */
  raceLabel: string;
  onClose: () => void;
}

function pct(p: number): string {
  return `${(p * 100).toFixed(0)}%`;
}

export default function DriverDetailSheet({
  entry,
  driverStandings,
  raceLabel,
  onClose,
}: Props) {
  const reduced = useReducedMotion();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);

  const record = useMemo(
    () => (entry ? driverStandings.find((d) => d.code === entry.code) : undefined),
    [entry, driverStandings],
  );

  // Escape to close + simple focus trap; restore focus to the prior element.
  useEffect(() => {
    if (!entry) return;
    lastFocusedRef.current = document.activeElement as HTMLElement | null;
    closeButtonRef.current?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const root = dialogRef.current;
      if (!root) return;
      const focusable = root.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
      lastFocusedRef.current?.focus?.();
    };
  }, [entry, onClose]);

  if (!entry) return null;

  // Cumulative pointsHistory → per-round delta for a legible "form" signal.
  const history = record?.pointsHistory ?? [];
  const perRoundDelta = history.map((cum, i) => (i === 0 ? cum : cum - history[i - 1]));
  const chartData = perRoundDelta.map((delta, i) => ({ round: `R${i + 1}`, delta }));
  const recentForm = perRoundDelta.slice(-3).reduce((a, b) => a + b, 0);

  const teamColor = entry.teamColor || "var(--accent)";

  const markets: Array<{ label: string; value: string }> = [
    { label: "Win", value: pct(entry.pWin) },
    { label: "Podium", value: pct(entry.pPodium) },
    { label: "Top 6", value: pct(entry.pTop6) },
    { label: "Top 10", value: pct(entry.pTop10) },
  ];

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 sm:p-6"
      style={{ background: "rgba(0,0,0,0.82)" }}
      onClick={onClose}
      role="presentation"
    >
      <motion.div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`${entry.name} — ${raceLabel} forecast`}
        initial={reduced ? false : { opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.22 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg border border-[color:var(--hairline-strong)] bg-[color:var(--surface-card)]"
        style={{ borderTop: `2px solid ${teamColor}` }}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-[color:var(--hairline)] px-5 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <DriverPortrait
              driver={entry.code}
              driverFullName={entry.name}
              team={entry.team}
              teamColor={entry.teamColor}
              headshotUrl={entry.headshotUrl}
              size={48}
            />
            <div className="min-w-0">
              <p className="title-md truncate">{entry.name}</p>
              <p className="body-sm text-[color:var(--muted)]">
                {entry.team} · Predicted P{entry.position}
              </p>
            </div>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close driver detail"
            className="btn-icon-bugatti shrink-0"
          >
            ✕
          </button>
        </div>

        <div className="space-y-6 px-5 py-5 sm:px-6">
          {/* Markets */}
          <div>
            <p className="eyebrow mb-3">{raceLabel} forecast</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {markets.map((m) => (
                <div
                  key={m.label}
                  className="border border-[color:var(--hairline)] p-3 text-center"
                >
                  <div className="font-mono font-tabular text-lg text-[color:var(--ink)]">
                    {m.value}
                  </div>
                  <div className="eyebrow mt-1">{m.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Projected finish */}
          <div className="grid grid-cols-2 gap-2">
            <div className="border border-[color:var(--hairline)] p-3">
              <div className="eyebrow mb-1">Mean finish</div>
              <div className="font-mono font-tabular text-lg text-[color:var(--ink)]">
                P{entry.meanFinish.toFixed(1)}
              </div>
            </div>
            <div className="border border-[color:var(--hairline)] p-3">
              <div className="eyebrow mb-1">Finish range</div>
              <div className="font-mono font-tabular text-lg text-[color:var(--ink)]">
                P{entry.finishRangeLow}–P{entry.finishRangeHigh}
              </div>
            </div>
          </div>

          {/* Season form */}
          {record ? (
            <div>
              <div className="mb-2 flex items-baseline justify-between">
                <p className="eyebrow">Season form (points per round)</p>
                <span
                  className="font-mono font-tabular text-xs"
                  style={{
                    color:
                      recentForm >= 25
                        ? "var(--accent-positive)"
                        : recentForm >= 10
                          ? "var(--accent)"
                          : "var(--muted)",
                  }}
                >
                  last 3: +{recentForm}
                </span>
              </div>
              <div className="mb-3 grid grid-cols-3 gap-2 text-center">
                {[
                  { label: "Points", value: record.points },
                  { label: "Wins", value: record.wins },
                  { label: "Podiums", value: record.podiums },
                ].map((s) => (
                  <div key={s.label} className="border border-[color:var(--hairline)] py-2">
                    <div className="font-mono font-tabular text-lg font-bold text-[color:var(--ink)]">
                      {s.value}
                    </div>
                    <div className="eyebrow mt-0.5">{s.label}</div>
                  </div>
                ))}
              </div>
              <div style={{ width: "100%", height: 72 }}>
                {chartData.length > 0 ? (
                  <ResponsiveContainer>
                    <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                      <XAxis
                        dataKey="round"
                        tick={{ fill: "var(--muted)", fontSize: 9 }}
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
                  <p className="body-sm py-4 text-[color:var(--muted)]">No race results yet.</p>
                )}
              </div>
            </div>
          ) : (
            <p className="body-sm text-[color:var(--muted)]">
              No season standings record for {entry.code} yet.
            </p>
          )}
        </div>
      </motion.div>
    </div>
  );
}
