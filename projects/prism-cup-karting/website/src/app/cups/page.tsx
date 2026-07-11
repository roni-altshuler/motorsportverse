import type { Metadata } from "next";
import { Trophy } from "lucide-react";

import { getAllCups, getLeagueData } from "@/lib/data";
import type { RaceReport } from "@/lib/types";

export const metadata: Metadata = {
  title: "Cups & Standings — Prism Cup Karting",
  description:
    "Four simulated cups, sixteen races: classifications, item-event highlights and the season standings. A fan-made simulated league.",
};

function RaceCard({ race }: { race: RaceReport }) {
  const podium = race.classification.slice(0, 3);
  return (
    <div className="card p-5">
      <div className="flex items-baseline justify-between gap-3 mb-4">
        <h4 className="title-sm" style={{ color: "var(--ink)" }}>
          {race.trackName}
        </h4>
        <span className="caption-uppercase shrink-0">{race.laps} laps</span>
      </div>

      <div className="flex flex-col gap-2 mb-5">
        {podium.map((row) => (
          <div key={row.racerId} className="flex items-center gap-3">
            <span className={`position-badge p${row.position}`}>P{row.position}</span>
            <span
              className="inline-block w-2 h-2 rounded-full shrink-0"
              style={{ background: row.color }}
            />
            <span className="body-sm truncate" style={{ color: "var(--body-strong)" }}>
              {row.name}
            </span>
            <span className="ml-auto font-mono text-[11px] font-tabular" style={{ color: "var(--muted)" }}>
              +{row.points}
            </span>
          </div>
        ))}
      </div>

      <p className="mono-label mb-2">Highlights</p>
      <ul className="flex flex-col gap-1.5 mb-4">
        {race.highlights.map((h, i) => (
          <li key={i} className="body-sm flex gap-2" style={{ color: "var(--muted)" }}>
            <span className="font-mono text-[10px] mt-1 shrink-0" style={{ color: "var(--accent-prism-bright)" }}>
              L{h.lap}
            </span>
            {h.text}
          </li>
        ))}
      </ul>

      <details className="deep-dive-section">
        <summary className="deep-dive-summary">Full classification</summary>
        <div className="deep-dive-section-body">
          <table className="w-full text-sm font-serif">
            <tbody>
              {race.classification.map((row) => (
                <tr key={row.racerId} className="border-b last:border-b-0" style={{ borderColor: "var(--hairline)" }}>
                  <td className="py-1.5 pr-3 font-mono text-[11px] font-tabular" style={{ color: "var(--muted)" }}>
                    P{row.position}
                  </td>
                  <td className="py-1.5" style={{ color: "var(--body)" }}>
                    {row.name}
                  </td>
                  <td className="py-1.5 pl-3 text-right font-mono text-[11px] font-tabular" style={{ color: "var(--muted)" }}>
                    {row.points} pts
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

export default function CupsPage() {
  const league = getLeagueData();
  const cups = getAllCups();

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
      <p className="eyebrow mb-3" style={{ color: "var(--accent-prism-bright)" }}>
        Season one · 4 cups · 16 races
      </p>
      <h1 className="display-lg mb-4">Cups & Standings</h1>
      <p className="body-md max-w-2xl mb-14">
        Every race below came out of the seeded season simulator — same points,
        same items, same rubber-banding you can run yourself on the home page.
        {" "}{league.champion.name} took the overall title with {league.champion.points} points.
      </p>

      {/* ── Season standings ────────────────────────────────────────── */}
      <section className="mb-20">
        <h2 className="section-heading">Overall standings</h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm font-serif" style={{ minWidth: 560 }}>
            <thead>
              <tr className="text-left" style={{ borderBottom: "1px solid var(--hairline)" }}>
                {["", "Racer", "Class", "Wins", "Podiums", "Best", "Points"].map((h, i) => (
                  <th key={i} className="mono-label py-3 px-4 font-normal">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {league.standings.map((row) => (
                <tr
                  key={row.racerId}
                  className="border-b last:border-b-0 racer-stripe"
                  style={
                    {
                      borderColor: "var(--hairline)",
                      "--racer-color": row.color,
                    } as React.CSSProperties
                  }
                >
                  <td className="py-2.5 px-4">
                    <span className={`position-badge ${row.rank <= 3 ? `p${row.rank}` : "points"}`}>
                      {row.rank}
                    </span>
                  </td>
                  <td className="py-2.5 px-4" style={{ color: "var(--body-strong)" }}>
                    {row.name}
                  </td>
                  <td className="py-2.5 px-4 caption-uppercase">{row.weightClass}</td>
                  <td className="py-2.5 px-4 font-mono text-[12px] font-tabular" style={{ color: "var(--body)" }}>
                    {row.wins}
                  </td>
                  <td className="py-2.5 px-4 font-mono text-[12px] font-tabular" style={{ color: "var(--body)" }}>
                    {row.podiums}
                  </td>
                  <td className="py-2.5 px-4 font-mono text-[12px] font-tabular" style={{ color: "var(--body)" }}>
                    P{row.bestFinish}
                  </td>
                  <td className="py-2.5 px-4 font-mono text-[12px] font-tabular" style={{ color: "var(--ink)" }}>
                    {row.points}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Cup by cup ──────────────────────────────────────────────── */}
      {cups.map((cup) => (
        <section key={cup.number} className="mb-20">
          <div className="flex items-center gap-3 mb-2">
            <Trophy className="w-5 h-5" style={{ color: "var(--accent-podium-1)" }} />
            <h2 className="display-sm">{cup.name}</h2>
          </div>
          <p className="caption-uppercase mb-6">
            Winner: {cup.standings[0].name} · {cup.standings[0].points} pts
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            {cup.races.map((race, i) => (
              <RaceCard key={`${cup.id}-${i}`} race={race} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
