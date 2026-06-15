import type { Metadata } from "next";

import { getF2Data } from "@/lib/f2data";

export const metadata: Metadata = { title: "Calendar — RaceIQ F2" };

export default function CalendarPage() {
  const data = getF2Data();
  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-3xl font-bold tracking-tight text-[var(--ink)]">{data.season} calendar</h1>
      <p className="mt-3 text-[var(--ink-muted)]">
        {data.completedRounds} rounds complete · {data.totalRounds - data.completedRounds} remaining.
      </p>
      <ol className="mt-10 space-y-2">
        {data.calendar.map((r) => (
          <li
            key={r.round}
            className="flex items-center justify-between rounded-[var(--radius-md)] border border-[var(--hairline)] bg-[var(--surface)] px-5 py-4"
          >
            <div className="flex items-center gap-4">
              <span className="w-8 text-sm font-bold text-[var(--ink-dim)]">R{r.round}</span>
              <div>
                <p className="font-semibold text-[var(--ink)]">{r.name}</p>
                {r.country && <p className="text-xs text-[var(--ink-dim)]">{r.country}</p>}
              </div>
            </div>
            <span
              className="rounded-full px-2.5 py-1 text-xs font-medium"
              style={
                r.completed
                  ? { color: "var(--ink-dim)", border: "1px solid var(--hairline)" }
                  : {
                      color: "var(--accent)",
                      border: "1px solid color-mix(in srgb, var(--accent) 40%, transparent)",
                    }
              }
            >
              {r.completed ? "Completed" : "Upcoming"}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
