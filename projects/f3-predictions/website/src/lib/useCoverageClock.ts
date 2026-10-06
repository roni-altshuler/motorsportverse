"use client";

import { useEffect, useState } from "react";

/** Seed static markup with build time, then recheck at hydration and hourly. */
export function useCoverageClock(asOf: string) {
  const [now, setNow] = useState(asOf);
  useEffect(() => {
    const tick = () => setNow(new Date().toISOString());
    const initial = window.setTimeout(tick, 0);
    const timer = window.setInterval(tick, 60 * 60 * 1000);
    return () => { window.clearTimeout(initial); window.clearInterval(timer); };
  }, []);
  return now;
}
