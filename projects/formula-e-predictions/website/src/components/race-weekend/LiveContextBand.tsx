"use client";

/**
 * Race-weekend live context band — Formula E port of the F1 flagship's band.
 *
 * Sticky strip just below the navbar that surfaces the next round's context.
 * FE has no live-timing or weather feed (data reality), so this is a thinned
 * version: it shows the next upcoming E-Prix with a countdown, its venue kind
 * (street vs circuit) and a freshness indicator, driven by the client-side
 * fe.json loader.
 *
 * Visibility: renders whenever the season still has an upcoming round; returns
 * null once every round is completed (or before data has loaded).
 */
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useFEData } from "@/lib/feclient";
import type { CalendarRound } from "@/types/fe";

const MS_PER_DAY = 24 * 60 * 60 * 1000;

function countdownLabel(targetIso: string | undefined, now: Date): string {
  if (!targetIso) return "Upcoming";
  const target = new Date(targetIso).getTime();
  if (Number.isNaN(target)) return "Upcoming";
  const ms = target - now.getTime();
  if (ms <= 0) return "Live · in progress";
  const days = Math.floor(ms / MS_PER_DAY);
  const hours = Math.floor((ms % MS_PER_DAY) / (60 * 60 * 1000));
  const mins = Math.floor((ms % (60 * 60 * 1000)) / (60 * 1000));
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

export default function LiveContextBand() {
  const data = useFEData();
  const [now, setNow] = useState<Date>(() => new Date());

  // Re-tick the countdown every 30s so it stays accurate while open.
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  const nextRound: CalendarRound | null = useMemo(() => {
    if (!data) return null;
    return data.calendar.find((r) => !r.completed) ?? null;
  }, [data]);

  if (!data || !nextRound) return null;

  const targetIso = nextRound.raceDate;
  const label = countdownLabel(targetIso, now);
  const isLive = label.startsWith("Live");

  return (
    <div
      className="sticky top-[60px] z-40 border-b"
      style={{ background: "var(--surface)", borderColor: "var(--border)" }}
      aria-label="Next-round context"
    >
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-2 text-sm sm:px-6 lg:px-8">
        <Link
          href={`/race/${nextRound.round}`}
          className="group inline-flex items-center gap-2 font-semibold text-[color:var(--text-primary)] transition-colors hover:text-[color:var(--accent-live)]"
        >
          <span className="hidden sm:inline">
            R{nextRound.round} · {nextRound.name}
          </span>
          <span className="sm:hidden">R{nextRound.round}</span>
        </Link>

        <span
          className="inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide"
          style={{
            borderColor: isLive ? "var(--accent-live)" : "var(--border)",
            color: isLive ? "var(--accent-live)" : "var(--text-secondary)",
          }}
        >
          {isLive ? "LIVE" : `Next · ${label}`}
        </span>

        <span className="hidden text-[color:var(--text-muted)] md:inline">
          {nextRound.kind === "street" ? "Street Circuit" : "Permanent Circuit"}
        </span>

        <div className="ml-auto flex items-center gap-2 text-[color:var(--text-muted)]">
          <span
            className="inline-block h-1.5 w-1.5 rounded-full"
            style={{ background: "var(--accent-positive)" }}
            aria-hidden
          />
          <span className="hidden sm:inline">Forecast data</span>
          <span className="sm:hidden">Live</span>
        </div>
      </div>
    </div>
  );
}
