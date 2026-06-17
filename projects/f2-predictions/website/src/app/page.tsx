import Link from "next/link";

import { DriverHeadshot } from "@/components/ui/DriverHeadshot";
import { getF2Data, teamColor } from "@/lib/f2data";
import { getRaceArt } from "@/lib/raceArt";

export default function HomePage() {
  const data = getF2Data();
  const leader = data.championship[0];
  const topTitle = data.championship.slice(0, 5);
  const next = data.nextPrediction;
  const acc = data.seasonAccuracy;
  const nextRound = next ? data.calendar.find((c) => c.round === next.round) : null;
  const nextArt = nextRound ? getRaceArt(nextRound.key) : null;

  return (
    <div className="mx-auto max-w-6xl px-6">
      {/* Hero */}
      <section className="relative overflow-hidden py-20 sm:py-28">
        <div
          className="pointer-events-none absolute inset-0 -z-10"
          aria-hidden
          style={{
            background:
              "radial-gradient(80% 120% at 75% -10%, color-mix(in srgb, var(--accent) 18%, transparent), transparent 55%)",
          }}
        />
        <p className="eyebrow mb-4">RaceIQ · Formula 2 · {data.season}</p>
        <h1 className="font-display max-w-3xl text-5xl font-bold leading-[1.02] tracking-tight text-[var(--ink)] sm:text-7xl">
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
            className="font-mono rounded-full px-5 py-2.5 text-sm font-semibold tracking-wide transition-transform hover:scale-[1.03] motion-reduce:transition-none motion-reduce:hover:scale-100"
            style={{ color: "var(--accent-ink)", backgroundColor: "var(--accent)" }}
          >
            Next-round prediction
          </Link>
          <Link
            href="/standings"
            className="font-mono rounded-full border border-[var(--hairline-strong)] px-5 py-2.5 text-sm font-semibold tracking-wide text-[var(--ink)] hover:border-[var(--accent)]"
          >
            Championship standings
          </Link>
          {acc && acc.roundsScored > 0 && (
            <Link
              href="/accuracy"
              className="font-mono rounded-full border border-[var(--hairline-strong)] px-5 py-2.5 text-sm font-semibold tracking-wide text-[var(--ink-muted)] hover:border-[var(--accent)] hover:text-[var(--ink)]"
            >
              Podium accuracy{" "}
              <span className="font-tabular">
                {acc.podiumHitRate != null ? `${(acc.podiumHitRate * 100).toFixed(0)}%` : "—"}
              </span>{" "}
              →
            </Link>
          )}
        </div>

        {/* Quick season stats strip */}
        <div className="mt-12 grid max-w-2xl grid-cols-2 gap-px overflow-hidden rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--hairline)] sm:grid-cols-4">
          <Stat label="Rounds run" value={`${data.completedRounds}/${data.totalRounds}`} />
          <Stat
            label="Winner hit"
            value={acc?.winnerHitRate != null ? `${(acc.winnerHitRate * 100).toFixed(0)}%` : "—"}
          />
          <Stat
            label="Podium hit"
            value={acc?.podiumHitRate != null ? `${(acc.podiumHitRate * 100).toFixed(0)}%` : "—"}
          />
          <Stat
            label="Mean error"
            value={acc?.meanPositionError != null ? acc.meanPositionError.toFixed(1) : "—"}
          />
        </div>
      </section>

      {/* Title fight */}
      <section className="pb-12">
        <p className="eyebrow mb-2">Title fight</p>
        <h2 className="font-display mb-6 text-2xl font-semibold text-[var(--ink)]">
          Who the model backs for the crown
        </h2>
        {leader && (
          <div
            className="mb-6 flex items-center gap-5 rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] p-6"
            style={{ borderLeft: `4px solid ${teamColor(leader.team)}` }}
          >
            <DriverHeadshot code={leader.code} teamColor={teamColor(leader.team)} size={64} />
            <div className="min-w-0">
              <p className="mono-label">Championship favourite</p>
              <p className="font-display mt-1 text-3xl font-bold text-[var(--ink)]">{leader.name}</p>
              <p className="text-[var(--ink-muted)]">{leader.team}</p>
            </div>
            <div className="ml-auto text-right">
              <p className="font-tabular text-4xl font-bold" style={{ color: "var(--accent)" }}>
                {(leader.pTitle * 100).toFixed(1)}%
              </p>
              <p className="font-tabular mt-1 text-xs text-[var(--ink-dim)]">
                {leader.currentPoints} pts · proj {leader.projMean.toFixed(0)} (
                {leader.projP10.toFixed(0)}–{leader.projP90.toFixed(0)})
              </p>
            </div>
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
              <p className="font-tabular mt-2 text-lg font-bold" style={{ color: "var(--accent)" }}>
                {(t.pTitle * 100).toFixed(1)}%
              </p>
            </div>
          ))}
        </div>
      </section>

      {next && (
        <section className="pb-24">
          <div className="flex items-end justify-between">
            <div>
              <p className="eyebrow mb-2">Next up</p>
              <h2 className="font-display text-2xl font-semibold text-[var(--ink)]">
                Round {next.round}: {next.venueName}
              </h2>
            </div>
            <Link href={`/race/${next.round}`} className="font-mono text-sm text-[var(--accent)]">
              Sprint + feature detail →
            </Link>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
            {/* Circuit aerial */}
            <Link
              href={`/race/${next.round}`}
              className="group relative block aspect-[16/9] overflow-hidden rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface-2)]"
            >
              {nextArt ? (
                <div
                  className="absolute inset-0 bg-cover bg-center transition-transform duration-500 group-hover:scale-[1.04] motion-reduce:transition-none motion-reduce:group-hover:scale-100"
                  style={{ backgroundImage: `url(${nextArt.src})` }}
                  role="img"
                  aria-label={nextArt.credit}
                />
              ) : (
                <div
                  className="absolute inset-0"
                  style={{
                    background:
                      "radial-gradient(120% 120% at 80% 0%, color-mix(in srgb, var(--accent) 22%, transparent), transparent 60%), var(--surface-2)",
                  }}
                  aria-hidden
                />
              )}
              <div
                className="absolute inset-0"
                style={{
                  background:
                    "linear-gradient(180deg, transparent 30%, color-mix(in srgb, var(--canvas) 75%, transparent) 100%)",
                }}
                aria-hidden
              />
              <p className="font-display absolute inset-x-4 bottom-3 text-xl font-bold text-[var(--ink)]">
                {next.venueName}
              </p>
            </Link>

            {/* Predicted podium */}
            <div className="grid content-start gap-3">
              {next.race.slice(0, 3).map((r, i) => (
                <div
                  key={r.code}
                  className="flex items-center gap-3 rounded-[var(--radius-md)] border border-[var(--hairline)] bg-[var(--surface)] p-4"
                  style={{ borderLeft: `3px solid ${teamColor(r.team)}` }}
                >
                  <span className="font-display text-2xl font-bold text-[var(--ink-dim)]">
                    P{i + 1}
                  </span>
                  <DriverHeadshot code={r.code} teamColor={teamColor(r.team)} size={38} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-[var(--ink)]">{r.name}</p>
                    <p className="truncate text-xs text-[var(--ink-dim)]">{r.team}</p>
                  </div>
                  <span className="font-tabular text-right text-sm text-[var(--ink-muted)]">
                    <span className="font-bold" style={{ color: "var(--accent)" }}>
                      {(r.pWin * 100).toFixed(0)}%
                    </span>
                    <br />
                    win
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[var(--surface)] p-4">
      <p className="mono-label">{label}</p>
      <p className="font-display font-tabular mt-1 text-2xl font-bold text-[var(--ink)]">{value}</p>
    </div>
  );
}
