"use client";

import { useEffect, useState } from "react";

interface HeroCountdownProps {
  /** ISO date string of the next feature race (YYYY-MM-DD or full ISO). */
  targetDate: string;
  className?: string;
}

const MS_PER_DAY = 24 * 60 * 60 * 1000;

function formatCountdown(targetIso: string, now: Date): string {
  const target = new Date(targetIso).getTime();
  if (Number.isNaN(target)) return "";
  const ms = target - now.getTime();
  if (ms <= 0) return "this weekend";
  const days = Math.floor(ms / MS_PER_DAY);
  const hours = Math.floor((ms % MS_PER_DAY) / (60 * 60 * 1000));
  if (days > 0) return `in ${days}d ${hours}h`;
  return `in ${hours}h`;
}

/**
 * Live countdown to the next round's feature race. The home page is a static
 * export, so the countdown is computed client-side on mount (and refreshed
 * hourly) rather than frozen at build time. Until mount it renders nothing so
 * SSR/no-JS never shows a stale value. Fed the date string as a prop — it never
 * imports the fs-based loader.
 */
export default function HeroCountdown({ targetDate, className }: HeroCountdownProps) {
  const [label, setLabel] = useState<string>("");

  useEffect(() => {
    const tick = () => setLabel(formatCountdown(targetDate, new Date()));
    tick();
    const id = setInterval(tick, 60 * 60 * 1000);
    return () => clearInterval(id);
  }, [targetDate]);

  if (!label) return null;
  return <span className={className}>{label}</span>;
}
