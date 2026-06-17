import type { Metadata } from "next";
import Link from "next/link";

import { PodiumProbabilityChart } from "@/components/charts/PodiumProbabilityChart";
import { DriverHeadshot } from "@/components/ui/DriverHeadshot";
import { getF2Data, teamColor } from "@/lib/f2data";

export const metadata: Metadata = { title: "Predictions — RaceIQ F2" };

export default function PredictionsPage() {
  const data = getF2Data();
  const next = data.nextPrediction;

  if (!next) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="font-display text-3xl font-bold text-[var(--ink)]">Predictions</h1>
        <p className="mt-3 text-[var(--ink-muted)]">The season is complete — no upcoming round.</p>
      </div>
    );
  }

  const maxWin = Math.max(...next.race.map((r) => r.pWin), 0.0001);
  const top3 = next.race.slice(0, 3);

  return (
    <div className="mx-auto max-w-5xl px-6 py-16">
      <p className="eyebrow">Round {next.round} · Next up</p>
      <h1 className="font-display mt-2 text-4xl font-bold tracking-tight text-[var(--ink)] sm:text-5xl">
        {next.venueName} — race forecast
      </h1>
      <p className="mt-3 max-w-2xl text-[var(--ink-muted)]">
        Predicted feature-race finishing order with win and podium probabilities, plus the projected
        qualifying order. Estimates from the MotorsportVerse core — not betting advice.
      </p>

      {/* Predicted podium hero trio */}
      <section className="mt-10 grid gap-3 sm:grid-cols-3">
        {top3.map((r, i) => (
          <div
            key={r.code}
            className="relative overflow-hidden rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-5"
            style={{ borderTop: `3px solid ${teamColor(r.team)}` }}
          >
            <span className="font-display absolute right-4 top-3 text-5xl font-bold text-[color-mix(in_srgb,var(--ink)_8%,transparent)]">
              P{i + 1}
            </span>
            <DriverHeadshot code={r.code} teamColor={teamColor(r.team)} size={44} />
            <p className="mt-3 text-base font-semibold text-[var(--ink)]">{r.name}</p>
            <p className="text-xs text-[var(--ink-dim)]">{r.team}</p>
            <p className="font-tabular mt-3 text-sm text-[var(--ink-muted)]">
              <span className="text-lg font-bold" style={{ color: "var(--accent)" }}>
                {(r.pWin * 100).toFixed(0)}%
              </span>{" "}
              win · {(r.pPodium * 100).toFixed(0)}% podium
            </p>
          </div>
        ))}
      </section>

      {/* Win vs podium board */}
      <section className="mt-12 rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-5 sm:p-6">
        <PodiumProbabilityChart
          rows={next.race.slice(0, 12).map((r) => ({
            code: r.code,
            name: r.name,
            team: r.team,
            teamColor: teamColor(r.team),
            pWin: r.pWin,
            pPodium: r.pPodium,
          }))}
        />
      </section>

      {/* Full predicted race result */}
      <h2 className="font-display mt-12 mb-4 text-xl font-semibold text-[var(--ink)]">
        Predicted race result
      </h2>
      <div className="space-y-1.5">
        {next.race.map((r) => (
          <div
            key={r.code}
            className="flex items-center gap-3 rounded-[var(--radius-sm)] border border-[var(--hairline)] bg-[var(--surface)] px-4 py-2.5"
          >
            <span className="font-tabular w-7 text-sm font-bold text-[var(--ink-dim)]">
              P{r.position}
            </span>
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
            <span className="font-tabular w-14 text-right text-xs text-[var(--ink-muted)]">
              {(r.pWin * 100).toFixed(0)}% win
            </span>
            <span className="font-tabular w-20 text-right text-xs text-[var(--ink-muted)]">
              {(r.pPodium * 100).toFixed(0)}% podium
            </span>
          </div>
        ))}
      </div>

      {/* Qualifying order */}
      <h2 className="font-display mt-12 mb-4 text-xl font-semibold text-[var(--ink)]">
        Projected qualifying
      </h2>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {next.qualifying.map((q) => (
          <div
            key={q.code}
            className="flex items-center gap-3 rounded-[var(--radius-sm)] border border-[var(--hairline)] bg-[var(--surface)] px-4 py-2"
            style={{ borderLeft: `3px solid ${teamColor(q.team)}` }}
          >
            <span className="font-tabular w-7 text-sm font-bold text-[var(--ink-dim)]">
              P{q.position}
            </span>
            <span className="text-sm text-[var(--ink)]">{q.name}</span>
            <span className="ml-auto text-xs text-[var(--ink-dim)]">{q.team}</span>
          </div>
        ))}
      </div>

      <div className="mt-12">
        <Link
          href={`/race/${next.round}`}
          className="font-mono text-sm font-medium tracking-wide text-[var(--accent)]"
        >
          Full sprint + feature detail for Round {next.round} →
        </Link>
      </div>
    </div>
  );
}
