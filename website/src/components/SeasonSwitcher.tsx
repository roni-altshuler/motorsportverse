"use client";

import { useSeason } from "@/lib/SeasonProvider";

/**
 * Compact season selector for the navbar utility strip.
 *
 * - One season available → a static "F1 <year>" chip (no interaction).
 * - Multiple seasons → a native <select> that switches the active season; the
 *   data layer re-resolves every fetch to that season's data root.
 */
export default function SeasonSwitcher() {
  const { year, index, hasMultiple, setYear } = useSeason();

  if (!hasMultiple) {
    return (
      <span
        className="eyebrow inline-flex items-center gap-1.5 px-2 py-0.5 border text-[color:var(--muted)]"
        style={{ borderColor: "var(--hairline)" }}
        title={`Formula 1 ${year} season`}
      >
        <span
          className="inline-block w-1.5 h-1.5 rounded-full"
          style={{ background: "var(--accent-f1-red)" }}
        />
        F1 {year}
      </span>
    );
  }

  const years = index ? [...index.available].sort((a, b) => b - a) : [year];

  return (
    <label
      className="eyebrow inline-flex items-center gap-1 px-2 py-0.5 border text-[color:var(--muted)] cursor-pointer hover:text-[color:var(--ink)] transition-colors"
      style={{ borderColor: "var(--hairline)" }}
      title="Switch season"
    >
      <span
        className="inline-block w-1.5 h-1.5 rounded-full"
        style={{ background: "var(--accent-f1-red)" }}
      />
      <span aria-hidden>F1</span>
      <select
        aria-label="Select season"
        value={year}
        onChange={(e) => setYear(parseInt(e.target.value, 10))}
        className="bg-transparent outline-none cursor-pointer text-[color:var(--ink)] eyebrow"
        style={{ appearance: "none", paddingRight: "0.75rem" }}
      >
        {years.map((y) => (
          <option key={y} value={y} className="text-black">
            {y}
            {index && y === index.current ? " · current" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
