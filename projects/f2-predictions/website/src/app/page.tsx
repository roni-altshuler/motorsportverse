import Link from "next/link";

import { getF2Data, teamColor } from "@/lib/f2data";

export default function HomePage() {
  const data = getF2Data();
  const leader = data.championship[0];
  const topTitle = data.championship.slice(0, 5);
  const next = data.nextPrediction;
  const acc = data.seasonAccuracy;

  return (
    <div className="mx-auto max-w-6xl px-6">
      <section className="py-16 sm:py-24">
        <p className="mb-4 text-sm font-medium uppercase tracking-[0.2em] text-[var(--accent)]">
          RaceIQ · Formula 2 · {data.season}
        </p>
        <h1 className="max-w-3xl text-4xl font-bold leading-tight tracking-tight text-[var(--ink)] sm:text-6xl">
          Formula 2, forecast.
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-[var(--ink-muted)]">
          Sprint, feature-race, and championship predictions for the FIA F2 championship — from a
          model built for a spec series, where driver skill rules and the sprint runs a reversed
          grid. {data.completedRounds} of {data.totalRounds} rounds complete. Same MotorsportVerse
          core that powers RaceIQ F1.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/predictions"
            className="rounded-full px-5 py-2.5 text-sm font-semibold"
            style={{ color: "var(--accent-ink)", backgroundColor: "var(--accent)" }}
          >
            Next-round prediction
          </Link>
          <Link
            href="/standings"
            className="rounded-full border border-[var(--hairline-strong)] px-5 py-2.5 text-sm font-semibold text-[var(--ink)] hover:border-[var(--accent)]"
          >
            Championship standings
          </Link>
          {acc && acc.roundsScored > 0 && (
            <Link
              href="/accuracy"
              className="rounded-full border border-[var(--hairline-strong)] px-5 py-2.5 text-sm font-semibold text-[var(--ink-muted)] hover:border-[var(--accent)] hover:text-[var(--ink)]"
            >
              Podium accuracy {acc.podiumHitRate != null ? `${(acc.podiumHitRate * 100).toFixed(0)}%` : "—"} →
            </Link>
          )}
        </div>
      </section>

      {/* Title fight */}
      <section className="pb-12">
        <h2 className="mb-6 text-2xl font-semibold text-[var(--ink)]">Title fight</h2>
        {leader && (
          <div className="mb-6 rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-6">
            <p className="text-xs uppercase tracking-wider text-[var(--ink-dim)]">
              Championship favourite
            </p>
            <p className="mt-1 text-3xl font-bold text-[var(--ink)]">{leader.name}</p>
            <p className="text-[var(--ink-muted)]">{leader.team}</p>
            <p className="mt-3 text-sm text-[var(--ink-muted)]">
              <span className="text-2xl font-bold" style={{ color: "var(--accent)" }}>
                {(leader.pTitle * 100).toFixed(1)}%
              </span>{" "}
              title probability · {leader.currentPoints} pts now · projected{" "}
              {leader.projMean.toFixed(0)} ({leader.projP10.toFixed(0)}–{leader.projP90.toFixed(0)})
            </p>
          </div>
        )}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {topTitle.map((t) => (
            <div
              key={t.code}
              className="rounded-[var(--radius-md)] border border-[var(--hairline)] bg-[var(--surface)] p-4"
              style={{ borderTop: `3px solid ${teamColor(t.team)}` }}
            >
              <p className="text-sm font-semibold text-[var(--ink)]">{t.name}</p>
              <p className="text-xs text-[var(--ink-dim)]">{t.team}</p>
              <p className="mt-2 text-lg font-bold" style={{ color: "var(--accent)" }}>
                {(t.pTitle * 100).toFixed(1)}%
              </p>
            </div>
          ))}
        </div>
      </section>

      {next && (
        <section className="pb-24">
          <div className="flex items-end justify-between">
            <h2 className="text-2xl font-semibold text-[var(--ink)]">
              Next up — Round {next.round}: {next.venueName}
            </h2>
            <Link href={`/race/${next.round}`} className="text-sm text-[var(--accent)]">
              Sprint + feature detail →
            </Link>
          </div>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {next.race.slice(0, 3).map((r) => (
              <div
                key={r.code}
                className="rounded-[var(--radius-md)] border border-[var(--hairline)] bg-[var(--surface)] p-4"
                style={{ borderLeft: `3px solid ${teamColor(r.team)}` }}
              >
                <p className="text-xs text-[var(--ink-dim)]">Predicted P{r.position}</p>
                <p className="text-base font-semibold text-[var(--ink)]">{r.name}</p>
                <p className="text-xs text-[var(--ink-dim)]">{r.team}</p>
                <p className="mt-2 text-sm text-[var(--ink-muted)]">
                  Win {(r.pWin * 100).toFixed(0)}% · Podium {(r.pPodium * 100).toFixed(0)}%
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
