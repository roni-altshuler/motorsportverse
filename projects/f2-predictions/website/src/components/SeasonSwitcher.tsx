"use client";

import { useF2Data } from "@/lib/f2client";

/**
 * Compact season selector for the navbar utility strip. Ported from RaceIQ F1.
 * F2 currently runs a single season (2026), so this renders the static
 * "F2 <year>" chip. The control is kept (mirrors F1) so an archived-seasons
 * index can light up the <select> branch later without UI churn.
 */
export default function SeasonSwitcher() {
  const data = useF2Data();
  const year = data?.season ?? 2026;

  return (
    <span
      className="eyebrow inline-flex items-center gap-1.5 px-2 py-0.5 border text-[color:var(--muted)]"
      style={{ borderColor: "var(--hairline)" }}
      title={`Formula 2 ${year} season`}
    >
      <span
        className="inline-block w-1.5 h-1.5 rounded-full"
        style={{ background: "var(--accent-f1-red)" }}
      />
      F2 {year}
    </span>
  );
}
