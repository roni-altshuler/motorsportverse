import Link from "next/link";

import RaceDay from "@/components/RaceDay";
import StandingsTable from "@/components/StandingsTable";
import { getLeague, getRoster, getRound } from "@/lib/data";

export default function HomePage() {
  const league = getLeague();
  const roster = getRoster();
  const finale = getRound(league.season.rounds);
  const featured = ["dash-calloway", "silas-merriweather", "hitch-barlow"]
    .map((slug) => roster.characters.find((c) => c.slug === slug))
    .filter((c): c is NonNullable<typeof c> => Boolean(c));

  return (
    <>
      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <section className="hero-valley">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
          <p className="eyebrow eyebrow-accent mb-4">A fan-made simulated racing story</p>
          <h1 className="display-xl max-w-3xl">
            Somewhere past the last gas station, the whole town paints its fences orange
          </h1>
          <p className="body-md mt-6 max-w-2xl text-[color:var(--body)]">
            Welcome to the Chrome Valley Racing League — twelve racers with more personality than
            horsepower, ten venues that were mostly not designed for racing, and one cup that
            every diner in the valley has an opinion about. Every result here comes out of a
            simulator; the heartbreak is procedurally generated and somehow still hurts.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="#race-day" className="btn-valley btn-valley-accent">
              Drop the green flag
            </a>
            <Link href="/garage/" className="btn-valley">
              Meet the racers
            </Link>
          </div>
          <div className="mt-12 flex flex-wrap gap-8">
            <div>
              <p className="display-md font-tabular">12</p>
              <p className="mono-label">original racers</p>
            </div>
            <div>
              <p className="display-md font-tabular">10</p>
              <p className="mono-label">invented venues</p>
            </div>
            <div>
              <p className="display-md font-tabular">1</p>
              <p className="mono-label">{league.league.trophy}</p>
            </div>
          </div>
        </div>
        <div className="hero-horizon" aria-hidden />
      </section>

      {/* ── Race Day — the interactive centerpiece ───────────────────── */}
      <section id="race-day" className="section-valley">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <p className="eyebrow mb-2">The centerpiece</p>
          <h2 className="section-heading">Race Day</h2>
          <p className="body-md mb-8 max-w-2xl">
            The same engine that simulated the season, running live in your browser. Showboats
            will wobble, pit crews will fumble, and somebody with a big heart will find three
            spots on the last lap. No two Sundays alike.
          </p>
          <RaceDay characters={roster.characters} venues={league.venues} />
        </div>
      </section>

      {/* ── The season so far ────────────────────────────────────────── */}
      <section className="section-valley hairline-divider-top bg-[color:var(--surface-soft)]">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <p className="eyebrow mb-2">{league.season.name}</p>
          <h2 className="section-heading">How the season went</h2>
          <div className="grid gap-8 lg:grid-cols-2">
            <div>
              <StandingsTable standings={league.standings.slice(0, 6)} compact />
              <Link href="/season/" className="link-valley body-sm mt-4 inline-block">
                Full standings, calendar and every round&apos;s story →
              </Link>
            </div>
            <div className="flex flex-col gap-4">
              {league.season.summary.map((line, i) => (
                <div key={i} className="card p-5">
                  <p className="body-md">{line}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="card mt-8 p-6">
            <p className="eyebrow eyebrow-accent mb-3">
              Last time out — round {finale.round}, {finale.venue.name}
            </p>
            <ul className="flex flex-col gap-2">
              {finale.story.map((bullet, i) => (
                <li key={i} className="body-md">
                  — {bullet}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ── Meet the valley ──────────────────────────────────────────── */}
      <section className="section-valley">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <p className="eyebrow mb-2">The cast</p>
          <h2 className="section-heading">Three reasons the diner never closes early</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {featured.map((c) => (
              <div
                key={c.slug}
                className="card racer-stripe p-6"
                style={{ "--racer-color": c.color } as React.CSSProperties}
              >
                <p className="mono-label">#{c.number} · {c.role}</p>
                <p className="title-md mt-2">{c.name}</p>
                <p className="body-sm mt-1 text-[color:var(--muted)]">
                  {c.car} · {c.hometown}
                </p>
                <p className="body-md mt-4">{c.bio}</p>
              </div>
            ))}
          </div>
          <Link href="/garage/" className="link-valley body-sm mt-6 inline-block">
            The whole garage, trait bars and all →
          </Link>
        </div>
      </section>
    </>
  );
}
