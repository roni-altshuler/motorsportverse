import Link from "next/link";
import type { RaceCalendarEntry, RoundData } from "@/types";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { resolveDriverHeadshot } from "@/lib/headshots";
import PublicationNotice from "./PublicationNotice";

export default function PublicationHoldPage({
  data,
  race,
}: {
  data: RoundData;
  race: RaceCalendarEntry;
}) {
  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <Link href="/calendar" className="link-bugatti">
        ← Season calendar
      </Link>
      <header className="my-8 border-b border-[var(--hairline)] pb-8">
        <p className="eyebrow mb-3">
          Formula 1 · Round {race.round} · {race.date}
        </p>
        <h1 className="display-md break-words">{race.name}</h1>
        <p className="body-md mt-3 text-[var(--muted)]">{race.circuit}</p>
      </header>
      <PublicationNotice data={data} race={race} />
      <div className="mt-10 space-y-10">
        {data.weekendResults?.sessions
          .filter((session) => session.rows.length > 0)
          .map((session) => (
            <section key={session.key} aria-label={session.label}>
              <div className="flex flex-wrap justify-between items-baseline gap-3 mb-4">
                <h2 className="section-heading">{session.label}</h2>
                <a
                  href={session.sourceUrl ?? undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="link-bugatti text-xs"
                >
                  Official source ↗
                </a>
              </div>
              {session.note && <p className="body-sm text-[var(--muted)] mb-4">{session.note}</p>}
              <div className="overflow-x-auto border-y border-[var(--hairline)]">
                <table className="w-full text-left" aria-label={session.label}>
                  <thead className="text-[var(--muted)]">
                    <tr className="eyebrow">
                      <th className="py-3 pr-3">Pos</th>
                      <th className="py-3">Driver</th>
                      <th className="py-3 pl-3 text-right">Time / status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {session.rows.map((row) => (
                      <tr key={row.driver} className="border-t border-[var(--hairline)]">
                        <td className="py-3 pr-3 font-mono text-sm">
                          {row.positionText || row.position}
                        </td>
                        <td className="py-3">
                          <div className="flex items-center gap-3">
                            <DriverPortrait
                              headshotUrl={resolveDriverHeadshot(row.driver)}
                              driver={row.driver}
                              driverFullName={row.driverFullName}
                              team={row.team}
                              teamColor={row.teamColor}
                              size={32}
                            />
                            <div>
                              <p className="body-sm text-[var(--ink)]">{row.driverFullName}</p>
                              <p className="text-xs text-[var(--muted)]">{row.team}</p>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 pl-3 text-right font-mono text-xs">
                          {row.q3 || row.q2 || row.q1 || row.time || row.status || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
      </div>
    </main>
  );
}
