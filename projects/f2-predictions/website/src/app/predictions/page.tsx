import type { Metadata } from "next";

import { getF2Data, teamColor } from "@/lib/f2data";

export const metadata: Metadata = { title: "Predictions — RaceIQ F2" };

export default function PredictionsPage() {
  const data = getF2Data();
  const next = data.nextPrediction;

  if (!next) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-3xl font-bold text-[var(--ink)]">Predictions</h1>
        <p className="mt-3 text-[var(--ink-muted)]">The season is complete — no upcoming round.</p>
      </div>
    );
  }

  const maxWin = Math.max(...next.race.map((r) => r.pWin), 0.0001);

  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <p className="text-sm font-medium uppercase tracking-[0.2em] text-[var(--accent)]">
        Round {next.round}
      </p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight text-[var(--ink)]">
        {next.venueName} — race forecast
      </h1>
      <p className="mt-3 text-[var(--ink-muted)]">
        Predicted finishing order with win and podium probabilities, plus the projected
        qualifying order. Estimates from the MotorsportVerse core, not betting advice.
      </p>

      {/* Race forecast with win-probability bars */}
      <h2 className="mt-12 mb-4 text-xl font-semibold text-[var(--ink)]">Predicted race result</h2>
      <div className="space-y-1.5">
        {next.race.map((r) => (
          <div
            key={r.code}
            className="flex items-center gap-3 rounded-[var(--radius-sm)] border border-[var(--hairline)] bg-[var(--surface)] px-4 py-2.5"
          >
            <span className="w-7 text-sm font-bold text-[var(--ink-dim)]">P{r.position}</span>
            <span
              className="h-6 w-1 rounded"
              style={{ backgroundColor: teamColor(r.team) }}
              aria-hidden
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-[var(--ink)]">{r.name}</p>
              <p className="truncate text-xs text-[var(--ink-dim)]">{r.team}</p>
            </div>
            <div className="hidden w-40 sm:block">
              <div className="h-2 w-full rounded-full bg-[var(--surface-3)]">
                <div
                  className="h-2 rounded-full"
                  style={{
                    width: `${(r.pWin / maxWin) * 100}%`,
                    backgroundColor: "var(--accent)",
                  }}
                />
              </div>
            </div>
            <span className="w-14 text-right text-xs text-[var(--ink-muted)]">
              {(r.pWin * 100).toFixed(0)}% win
            </span>
            <span className="w-20 text-right text-xs text-[var(--ink-muted)]">
              {(r.pPodium * 100).toFixed(0)}% podium
            </span>
          </div>
        ))}
      </div>

      {/* Qualifying order */}
      <h2 className="mt-12 mb-4 text-xl font-semibold text-[var(--ink)]">Projected qualifying</h2>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {next.qualifying.map((q) => (
          <div
            key={q.code}
            className="flex items-center gap-3 rounded-[var(--radius-sm)] border border-[var(--hairline)] bg-[var(--surface)] px-4 py-2"
            style={{ borderLeft: `3px solid ${teamColor(q.team)}` }}
          >
            <span className="w-7 text-sm font-bold text-[var(--ink-dim)]">P{q.position}</span>
            <span className="text-sm text-[var(--ink)]">{q.name}</span>
            <span className="ml-auto text-xs text-[var(--ink-dim)]">{q.team}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
