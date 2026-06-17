import type { Metadata } from "next";
import Link from "next/link";

import { getF2Data } from "@/lib/f2data";
import { getRaceArt } from "@/lib/raceArt";

export const metadata: Metadata = { title: "Calendar — RaceIQ F2" };

export default function CalendarPage() {
  const data = getF2Data();
  const remaining = data.totalRounds - data.completedRounds;

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <p className="eyebrow mb-3">Formula 2 · {data.season}</p>
      <h1 className="font-display text-4xl font-bold tracking-tight text-[var(--ink)] sm:text-5xl">
        {data.season} calendar
      </h1>
      <p className="mt-3 max-w-2xl text-[var(--ink-muted)]">
        {data.completedRounds} rounds complete · {remaining} remaining. Each weekend runs a reversed-grid
        sprint and a feature race — tap a round for the full forecast.
      </p>

      <ol className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {data.calendar.map((r) => {
          const art = getRaceArt(r.key);
          return (
            <li key={r.round}>
              <Link
                href={`/race/${r.round}`}
                className="group block overflow-hidden rounded-[var(--radius-lg)] border border-[var(--hairline)] bg-[var(--surface)] transition-colors hover:border-[var(--accent)]"
              >
                {/* Aerial circuit photo (or a styled placeholder if none) */}
                <div className="relative aspect-[16/9] overflow-hidden bg-[var(--surface-2)]">
                  {art ? (
                    <div
                      className="absolute inset-0 bg-cover bg-center transition-transform duration-500 group-hover:scale-[1.04] motion-reduce:transition-none motion-reduce:group-hover:scale-100"
                      style={{ backgroundImage: `url(${art.src})` }}
                      role="img"
                      aria-label={art.credit}
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
                  {/* legibility scrim */}
                  <div
                    className="absolute inset-0"
                    style={{
                      background:
                        "linear-gradient(180deg, color-mix(in srgb, var(--canvas) 10%, transparent) 0%, color-mix(in srgb, var(--canvas) 78%, transparent) 100%)",
                    }}
                    aria-hidden
                  />
                  <div className="absolute left-4 top-4 flex items-center gap-2">
                    <span className="font-mono rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--canvas)_70%,transparent)] px-2 py-0.5 text-xs font-semibold tracking-[0.14em] text-[var(--ink)] backdrop-blur">
                      R{r.round}
                    </span>
                    <span
                      className="rounded-full px-2 py-0.5 text-[11px] font-medium backdrop-blur"
                      style={
                        r.completed
                          ? {
                              color: "var(--ink-muted)",
                              background: "color-mix(in srgb, var(--canvas) 60%, transparent)",
                            }
                          : {
                              color: "var(--accent)",
                              background: "color-mix(in srgb, var(--accent) 14%, transparent)",
                            }
                      }
                    >
                      {r.completed ? "Completed" : "Upcoming"}
                    </span>
                  </div>
                  <div className="absolute inset-x-4 bottom-3">
                    <p className="font-display text-xl font-bold leading-none text-[var(--ink)]">
                      {r.name}
                    </p>
                    {r.country && (
                      <p className="mt-1 text-xs text-[var(--ink-muted)]">{r.country}</p>
                    )}
                  </div>
                </div>
              </Link>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
