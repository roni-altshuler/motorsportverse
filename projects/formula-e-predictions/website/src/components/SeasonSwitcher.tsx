"use client";

import { useSeason } from "@/lib/SeasonProvider";

/**
 * Compact season selector for the navbar utility strip. Ported from the F1
 * flagship's live switcher.
 *
 * - One season available → a static "FE <label>" chip (no interaction).
 * - Multiple seasons → a native <select> that switches the active season; the
 *   data layer re-resolves season-aware fetches to that season's data root.
 *
 * The accent token names are shared with F1 (--accent-f1-red) but repointed to
 * Formula E's electric blue in tokens.css — do not "fix" the variable name.
 */
export default function SeasonSwitcher() {
  const { year, index, hasMultiple, setYear } = useSeason();

  // Formula E seasons are split-year — prefer the index label ("2025-26").
  const labelFor = (y: number) =>
    index?.seasons.find((s) => s.year === y)?.label ?? String(y);

  if (!hasMultiple) {
    return (
      <span
        className="eyebrow inline-flex items-center gap-1.5 px-2 py-0.5 border text-[color:var(--muted)]"
        style={{ borderColor: "var(--hairline)" }}
        title={`Formula E ${labelFor(year)} season`}
      >
        <span
          className="inline-block w-1.5 h-1.5 rounded-full"
          style={{ background: "var(--accent-f1-red-hover)" }}
        />
        FE {labelFor(year)}
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
        style={{ background: "var(--accent-f1-red-hover)" }}
      />
      <span aria-hidden>FE</span>
      <select
        aria-label="Select season"
        value={year}
        onChange={(e) => setYear(parseInt(e.target.value, 10))}
        className="bg-transparent outline-none cursor-pointer text-[color:var(--ink)] eyebrow"
        style={{ appearance: "none", paddingRight: "0.75rem" }}
      >
        {years.map((y) => (
          <option key={y} value={y} className="text-black">
            {labelFor(y)}
            {index && y === index.current ? " · current" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
