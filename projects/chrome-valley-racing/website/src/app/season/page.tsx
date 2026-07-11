import type { Metadata } from "next";

import StandingsTable from "@/components/StandingsTable";
import { getAllRounds, getLeague } from "@/lib/data";

export const metadata: Metadata = {
  title: "The Season — Chrome Valley Racing League",
  description:
    "The full simulated season of the Chrome Valley Racing League — calendar, standings and a three-line story for every round.",
};

export default function SeasonPage() {
  const league = getLeague();
  const rounds = getAllRounds();
  const champion = league.season.champion;

  return (
    <section className="section-valley">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <p className="eyebrow eyebrow-accent mb-4">{league.season.name}</p>
        <h1 className="display-lg max-w-3xl">
          Ten Sundays, one cup, and a valley that talked about nothing else
        </h1>
        <p className="body-md mt-5 max-w-2xl">
          {champion.name} took {league.league.trophy} with {champion.points} points — but the
          standings only tell you who. The round-by-round stories below tell you how, and how
          close it came to going the other way.
        </p>

        {/* ── Calendar ─────────────────────────────────────────────────── */}
        <h2 className="section-heading mt-14">The calendar</h2>
        <div className="card overflow-x-auto">
          <table className="valley-table min-w-[560px]">
            <thead>
              <tr>
                <th>Rd</th>
                <th>Venue</th>
                <th>Kind</th>
                <th>Winner</th>
              </tr>
            </thead>
            <tbody>
              {league.calendar.map((entry) => (
                <tr key={entry.round}>
                  <td className="font-tabular text-[color:var(--muted)]">
                    {String(entry.round).padStart(2, "0")}
                  </td>
                  <td className="text-[color:var(--body-strong)]">{entry.venueName}</td>
                  <td>
                    <span className="status-pill status-pill-slate">{entry.kind}</span>
                  </td>
                  <td className="text-[color:var(--ink)]">{entry.winnerName}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ── Standings ────────────────────────────────────────────────── */}
        <h2 className="section-heading mt-14">Final standings</h2>
        <StandingsTable standings={league.standings} />

        {/* ── Round stories ────────────────────────────────────────────── */}
        <h2 className="section-heading mt-14">Every round, three lines at the counter</h2>
        <div className="grid gap-4 lg:grid-cols-2">
          {rounds.map((round) => (
            <article key={round.round} className="card p-6">
              <div className="flex items-baseline justify-between gap-4">
                <p className="title-sm">
                  Round {round.round} · {round.venue.name}
                </p>
                <p className="mono-label whitespace-nowrap">{round.venue.laps} laps</p>
              </div>
              <p className="eyebrow mt-1">{round.venue.kind}</p>
              <ul className="mt-4 flex flex-col gap-2">
                {round.story.map((bullet, i) => (
                  <li key={i} className="body-md">
                    — {bullet}
                  </li>
                ))}
              </ul>
              <div className="hairline-divider-top mt-5 flex flex-wrap gap-x-6 gap-y-1 pt-4">
                {round.results.slice(0, 3).map((r) => (
                  <span key={r.slug} className="mono-label">
                    P{r.position} {r.name}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
