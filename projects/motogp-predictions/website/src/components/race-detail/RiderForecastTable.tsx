"use client";

import { useId, useRef, useState } from "react";

import { DriverHeadshot } from "@/components/ui/DriverHeadshot";
import type { RaceBlock } from "@/types/motogp";

type SortBy = "position" | "pWin" | "pPodium";

function searchable(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function chance(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function RiderForecastTable({
  block,
  completed,
  onSelect,
}: {
  block: RaceBlock;
  completed: boolean;
  onSelect: (code: string) => void;
}) {
  const id = useId();
  const searchRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [manufacturer, setManufacturer] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("position");
  const raceLabel = block.raceType === "feature" ? "Grand Prix" : "Sprint";
  const manufacturers = [...new Set(block.classification.map((entry) => entry.team))].sort();
  const term = searchable(query.trim());
  const riders = block.classification
    .filter((entry) =>
      (!manufacturer || entry.team === manufacturer)
      && (!term || searchable(`${entry.name} ${entry.code}`).includes(term)),
    )
    .sort((a, b) =>
      (sortBy === "position" ? a.position - b.position : b[sortBy] - a[sortBy])
      || a.position - b.position
      || a.code.localeCompare(b.code),
    );
  const maxWin = Math.max(0.0001, ...block.classification.map((entry) => entry.pWin));
  const changed = query !== "" || manufacturer !== "" || sortBy !== "position";
  const controlClass = "min-h-11 w-full rounded-lg border border-[var(--hairline)] bg-[var(--surface)] px-3 py-2.5 text-sm text-[var(--ink)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]";

  return (
    <section aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`} className="mb-2 text-xl font-semibold text-[var(--ink)]">
        Rider forecasts
      </h2>
      <p className="mb-4 text-sm text-[var(--ink-muted)]">
        Predicted finish shows expected finishing order. Win chance estimates first place;
        podium chance estimates a top-three finish. Select a rider for their race forecast.
      </p>
      <div className="mb-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr]">
        <label className="grid gap-1.5 text-sm text-[var(--ink-muted)]" htmlFor={`${id}-search`}>
          Find a rider
          <input
            ref={searchRef}
            id={`${id}-search`}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Rider name or code"
            className={controlClass}
          />
        </label>
        <label className="grid gap-1.5 text-sm text-[var(--ink-muted)]" htmlFor={`${id}-manufacturer`}>
          Manufacturer
          <select
            id={`${id}-manufacturer`}
            value={manufacturer}
            onChange={(event) => setManufacturer(event.target.value)}
            className={controlClass}
          >
            <option value="">All manufacturers</option>
            {manufacturers.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
        <label className="grid gap-1.5 text-sm text-[var(--ink-muted)]" htmlFor={`${id}-sort`}>
          Sort riders by
          <select
            id={`${id}-sort`}
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value as SortBy)}
            className={controlClass}
          >
            <option value="position">Predicted finish</option>
            <option value="pWin">Win chance</option>
            <option value="pPodium">Podium chance</option>
          </select>
        </label>
      </div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p role="status" className="text-sm text-[var(--ink-muted)]">
          Showing {riders.length} of {block.classification.length} riders · {raceLabel}
        </p>
        <button
          type="button"
          disabled={!changed}
          onClick={() => {
            setQuery("");
            setManufacturer("");
            setSortBy("position");
            searchRef.current?.focus();
          }}
          className="min-h-11 rounded-lg border border-[var(--hairline)] px-3 py-2 text-sm text-[var(--ink)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] disabled:opacity-40"
        >
          Reset filters
        </button>
      </div>

      <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-[var(--hairline)]">
        <table className="w-full text-sm">
          <caption className="sr-only">{raceLabel} rider forecasts</caption>
          <thead>
            <tr className="bg-[var(--surface-2)] text-left text-xs uppercase tracking-wider text-[var(--ink-dim)]">
              <th scope="col" className="px-3 py-3 font-medium">
                <span className="sm:hidden" aria-hidden>Pred.</span>
                <span className="sr-only sm:not-sr-only">Predicted finish</span>
              </th>
              <th scope="col" className="px-3 py-3 font-medium">Rider</th>
              <th scope="col" className="hidden px-3 py-3 font-medium sm:table-cell">Win chance</th>
              <th scope="col" className="hidden px-3 py-3 font-medium sm:table-cell">Podium chance</th>
              <th scope="col" className="hidden px-3 py-3 font-medium md:table-cell">Range</th>
              <th scope="col" className="hidden px-3 py-3 font-medium lg:table-cell">Confidence</th>
              {completed && <th scope="col" className="px-3 py-3 text-right font-medium">Actual</th>}
            </tr>
          </thead>
          <tbody>
            {riders.length === 0 ? (
              <tr>
                <td colSpan={completed ? 7 : 6} className="px-4 py-8 text-center text-[var(--ink-muted)]">
                  No riders match these filters.
                </td>
              </tr>
            ) : riders.map((entry) => (
              <tr key={entry.code} className="border-t border-[var(--hairline)] bg-[var(--surface)] hover:bg-[var(--surface-2)] focus-within:bg-[var(--surface-2)]">
                <td
                  className="px-3 py-2.5 font-bold text-[var(--ink)]"
                  style={{ borderLeft: `3px solid ${entry.teamColor}` }}
                >
                  {entry.position}
                </td>
                <td className="px-3 py-2.5">
                  <button
                    type="button"
                    onClick={() => onSelect(entry.code)}
                    aria-label={`Open ${entry.name} forecast detail`}
                    className="flex min-h-11 w-full items-center gap-2.5 rounded-sm text-left focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent)]"
                  >
                    <DriverHeadshot code={entry.code} teamColor={entry.teamColor} size={30} />
                    <span className="min-w-0">
                      <span className="block [overflow-wrap:anywhere] font-medium text-[var(--ink)]">{entry.name}</span>
                      <span className="block text-xs text-[var(--ink-dim)]">{entry.team}</span>
                    </span>
                  </button>
                  <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[var(--ink-muted)] sm:hidden">
                    <span>Win {chance(entry.pWin)}</span>
                    <span>Podium {chance(entry.pPodium)}</span>
                  </div>
                </td>
                <td className="hidden px-3 py-2.5 sm:table-cell">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-16 overflow-hidden rounded-full bg-[var(--surface-3)]" aria-hidden>
                      <span className="block h-1.5 rounded-full" style={{ width: `${(entry.pWin / maxWin) * 100}%`, backgroundColor: "var(--accent)" }} />
                    </span>
                    <span className="tabular-nums text-[var(--ink-muted)]">{chance(entry.pWin)}</span>
                  </div>
                </td>
                <td className="hidden px-3 py-2.5 tabular-nums text-[var(--ink-muted)] sm:table-cell">{chance(entry.pPodium)}</td>
                <td className="hidden px-3 py-2.5 tabular-nums text-[var(--ink-muted)] md:table-cell">P{entry.finishRangeLow}–P{entry.finishRangeHigh}</td>
                <td className="hidden px-3 py-2.5 lg:table-cell">
                  <span className="rounded-full border border-[var(--hairline-strong)] px-2 py-0.5 text-xs text-[var(--ink-muted)]">{entry.confidence}</span>
                </td>
                {completed && (
                  <td className="px-3 py-2.5 text-right font-semibold text-[var(--ink)]">
                    {entry.actualPosition != null ? `P${entry.actualPosition}` : "—"}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
