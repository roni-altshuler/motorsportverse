"use client";

import { useState } from "react";

import ProgressionChart, {
  type ProgressionSeries,
} from "@/components/charts/ProgressionChart";

// Driver + team championship projection charts for the standings page. A tab
// toggle switches the shared ProgressionChart between the two entity types. The
// series are pre-built server-side (in the standings page) from the points
// progression reconstruction + projected totals, so this stays a thin client
// wrapper around the dependency-free SVG chart.
export function StandingsProgression({
  driverSeries,
  teamSeries,
  rounds,
  totalRounds,
}: {
  driverSeries: ProgressionSeries[];
  teamSeries: ProgressionSeries[];
  rounds: number[];
  totalRounds: number;
}) {
  const [view, setView] = useState<"drivers" | "teams">("drivers");
  const series = view === "drivers" ? driverSeries : teamSeries;

  return (
    <section className="mt-12 rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-5 sm:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">Championship projection</p>
          <h2 className="font-display mt-1 text-xl font-semibold text-[var(--ink)]">
            Points to season&rsquo;s end
          </h2>
        </div>
        <div className="flex gap-2">
          {(["drivers", "teams"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              className="rounded-full border px-3.5 py-1 text-xs font-medium capitalize"
              style={{
                color: view === v ? "var(--accent-ink)" : "var(--ink-muted)",
                backgroundColor: view === v ? "var(--accent)" : "transparent",
                borderColor: view === v ? "var(--accent)" : "var(--hairline)",
              }}
            >
              {v}
            </button>
          ))}
        </div>
      </div>
      <ProgressionChart series={series} rounds={rounds} totalRounds={totalRounds} />
      <p className="mt-3 text-xs text-[var(--ink-dim)]">
        Solid = points scored so far · dashed = projected at each entity&rsquo;s current pace. Top{" "}
        {series.length} shown.
      </p>
    </section>
  );
}
