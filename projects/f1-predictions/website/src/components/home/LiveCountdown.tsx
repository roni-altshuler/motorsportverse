"use client";

/**
 * LiveCountdown — a self-contained ticking countdown to an ISO target time.
 *
 * Owns its own `now` state + interval so only this small subtree re-renders
 * each tick (never the whole page it sits in). Reduced-motion users get a
 * calmer minute-granularity readout instead of a per-second D:H:M:S clock —
 * the interval and format both adapt, and the interval is always cleaned up.
 */
import { useEffect, useState } from "react";
import { useReducedMotion } from "@/lib/useReducedMotion";

const MS_PER_DAY = 24 * 60 * 60 * 1000;
const MS_PER_HOUR = 60 * 60 * 1000;
const MS_PER_MIN = 60 * 1000;

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function format(ms: number, withSeconds: boolean): string {
  if (ms <= 0) return "in progress";
  const days = Math.floor(ms / MS_PER_DAY);
  const hours = Math.floor((ms % MS_PER_DAY) / MS_PER_HOUR);
  const mins = Math.floor((ms % MS_PER_HOUR) / MS_PER_MIN);
  const secs = Math.floor((ms % MS_PER_MIN) / 1000);
  if (!withSeconds) {
    return days > 0 ? `in ${days}d ${hours}h` : `in ${hours}h ${pad(mins)}m`;
  }
  return days > 0
    ? `${days}d ${pad(hours)}:${pad(mins)}:${pad(secs)}`
    : `${pad(hours)}:${pad(mins)}:${pad(secs)}`;
}

interface LiveCountdownProps {
  /** ISO timestamp to count down to. */
  targetIso: string;
  className?: string;
}

export default function LiveCountdown({ targetIso, className }: LiveCountdownProps) {
  const reduced = useReducedMotion();
  const [ms, setMs] = useState<number>(
    () => new Date(targetIso).getTime() - Date.now(),
  );

  useEffect(() => {
    const tick = () => setMs(new Date(targetIso).getTime() - Date.now());
    tick();
    // Live seconds for everyone except reduced-motion users, who get a calm
    // minute cadence so nothing flickers.
    const id = window.setInterval(tick, reduced ? MS_PER_MIN : 1000);
    return () => window.clearInterval(id);
  }, [targetIso, reduced]);

  // Default aria politeness (off) — the surrounding copy already states the
  // date, so per-second updates never reach assistive tech.
  return <span className={className}>{format(ms, !reduced)}</span>;
}
