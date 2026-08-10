"use client";

import Link from "next/link";

import AddToCalendar from "@/components/AddToCalendar";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import SeasonRibbon from "@/components/calendar/SeasonRibbon";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { useSeasonWrcData } from "@/lib/wrcClient";
import { getRaceArt } from "@/lib/raceArt";
import { surfaceLabel } from "@/lib/surface";
import type { CalendarRound } from "@/types/wrc";

interface CalendarPageProps {
  season: number;
  totalRounds: number;
  completedRounds: number;
  calendar: CalendarRound[];
}

/**
 * WRC port of the RaceIQ F1 CalendarPage: a SeasonRibbon strip, a
 * surface-forward round-card grid, a 3-up season-stats row, and a
 * hairline-divided round list. Adapted to the WRC CalendarRound shape — each
 * round is a SINGLE rally at one location (no sprint, no qualifying, no
 * circuit), and its SURFACE (gravel / tarmac / snow) is the signature variable,
 * so every card and list row carries a colour-coded surface chip. If a
 * curated, verified stage photograph is ever added (via getRaceArt) it fronts
 * the card; otherwise the card falls back to a surface-tinted gradient.
 *
 * Multi-season: the page is baked with the CURRENT season's data (static
 * export); when the SeasonSwitcher selects an archived season, that season's
 * wrc.json overlays the baked props client-side (mirrors F1's useSeason wiring).
 */

/** Format the rally date as e.g. "22 Jan 2026" (UTC-safe). */
function formatRallyDate(iso?: string): string | null {
  if (!iso) return null;
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}
export default function CalendarPage({
  season: baseSeason,
  totalRounds: baseTotalRounds,
  completedRounds: baseCompletedRounds,
  calendar: baseCalendar,
}: CalendarPageProps) {
  const { data: seasonData, isArchived } = useSeasonWrcData();
  const overlay = isArchived && seasonData ? seasonData : null;
  const season = overlay?.season ?? baseSeason;
  const totalRounds = overlay?.totalRounds ?? baseTotalRounds;
  const completedRounds = overlay?.completedRounds ?? baseCompletedRounds;
  const calendar = overlay?.calendar ?? baseCalendar;
  const remaining = totalRounds - completedRounds;
  const lastCompleted = calendar.filter((r) => r.completed).reduce((m, r) => Math.max(m, r.round), 0);
  const nextRound = calendar.find((r) => !r.completed)?.round;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 section-bugatti">
      <div className="mb-12 max-w-3xl">
        <p className="eyebrow mb-4">WRC · {season} World Rally Championship</p>
        <h1 className="display-xl [font-weight:700] mb-4">Season Calendar</h1>
        <p className="body-md text-[color:var(--body)] mb-2">
          Every round of the {season} World Rally Championship — a forecast before each rally, the
          official classification after. Gravel, tarmac and snow, one classification per event.
        </p>
        <p className="body-sm text-[color:var(--muted)]">
          {totalRounds} rounds · {completedRounds} complete · {remaining} remaining
        </p>
        <div className="mt-6">
          <AddToCalendar
            races={calendar}
            season={season}
            variant="ghost"
            size="sm"
            label="Add full season to calendar"
          />
        </div>
      </div>

      <SeasonRibbon calendar={calendar} />

      {/* Surface-forward round-card grid */}
      <section className="mb-16" aria-labelledby="season-window-heading">
        <div className="flex items-baseline justify-between mb-6">
          <div>
            <p className="eyebrow mb-1">Season Window</p>
            <h2 id="season-window-heading" className="display-md">
              All {totalRounds} rounds, surface by surface
            </h2>
          </div>
        </div>
        <ol className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {calendar.map((r) => {
            const art = getRaceArt(r.key);
            const isNext = r.round === nextRound;
            const dateLabel = formatRallyDate(r.date);
            return (
              <li key={r.round}>
                <Link
                  href={`/race/${r.round}`}
                  className="group block overflow-hidden rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] transition-colors hover:border-[color:var(--accent)]"
                >
                  <div className="relative aspect-[16/9] overflow-hidden bg-[color:var(--surface-elevated)]">
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
                          background: `radial-gradient(120% 120% at 80% 0%, color-mix(in srgb, ${r.surfaceColor} 32%, transparent), transparent 60%), var(--surface-elevated)`,
                        }}
                        aria-hidden
                      />
                    )}
                    <div
                      className="absolute inset-0"
                      style={{
                        background:
                          "linear-gradient(180deg, color-mix(in srgb, var(--canvas) 10%, transparent) 0%, color-mix(in srgb, var(--canvas) 78%, transparent) 100%)",
                      }}
                      aria-hidden
                    />
                    <div className="absolute left-4 top-4 flex items-center gap-2">
                      <span className="font-mono rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--canvas)_70%,transparent)] px-2 py-0.5 text-xs font-semibold tracking-[0.14em] text-[color:var(--ink)] backdrop-blur">
                        R{r.round}
                      </span>
                      <span
                        className="rounded-full px-2 py-0.5 text-[11px] font-medium backdrop-blur"
                        style={
                          r.completed
                            ? {
                                color: "var(--muted)",
                                background: "color-mix(in srgb, var(--canvas) 60%, transparent)",
                              }
                            : {
                                color: "var(--accent)",
                                background: "color-mix(in srgb, var(--accent) 14%, transparent)",
                              }
                        }
                      >
                        {r.completed ? "Completed" : isNext ? "Next up" : "Upcoming"}
                      </span>
                    </div>
                    {/* Signature surface chip */}
                    <span
                      className="surface-chip absolute right-4 top-4 backdrop-blur"
                      data-surface={r.surface}
                      style={{ "--surface-color": r.surfaceColor } as React.CSSProperties}
                    >
                      {surfaceLabel(r.surface)}
                    </span>
                    <div className="absolute inset-x-4 bottom-3 flex items-center gap-3">
                      <CountryFlag country={r.country} size={28} className="shrink-0" />
                      <div className="min-w-0">
                        <p className="font-display text-xl font-bold leading-none text-[color:var(--ink)] truncate">
                          {r.name}
                        </p>
                        <p className="mt-1 text-xs text-[color:var(--muted)] truncate">
                          {[r.country, dateLabel].filter(Boolean).join(" · ")}
                        </p>
                      </div>
                    </div>
                  </div>
                </Link>
              </li>
            );
          })}
        </ol>
      </section>

      {/* Season stats row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-0 mb-16 mt-12 hairline-divider-top">
        <div className="row-spec sm:border-b-0 sm:pr-8 sm:border-r border-[color:var(--hairline)]">
          <p className="eyebrow mb-3">Rounds Complete</p>
          <div className="flex items-baseline gap-2">
            <span className="display-xl !text-[64px] !leading-none [font-weight:700] text-[color:var(--ink)]">
              <NumberTicker value={completedRounds} />
            </span>
            <span className="body-md text-[color:var(--muted)]">/ {totalRounds}</span>
          </div>
          <p className="body-sm text-[color:var(--muted)] mt-3">
            Rounds with results and forecasts published.
          </p>
        </div>
        <div className="row-spec sm:border-b-0 sm:px-8 sm:border-r border-[color:var(--hairline)]">
          <p className="eyebrow mb-3">Rounds Remaining</p>
          <span className="display-xl !text-[64px] !leading-none [font-weight:700] text-[color:var(--accent)]">
            <NumberTicker value={remaining} />
          </span>
          <p className="body-sm text-[color:var(--muted)] mt-3">
            Still to run before the title is settled.
          </p>
        </div>
        <div className="row-spec sm:border-b-0 sm:pl-8">
          <p className="eyebrow mb-3">Last Completed</p>
          <span className="display-xl !text-[64px] !leading-none [font-weight:700] text-[color:var(--ink)]">
            R<NumberTicker value={lastCompleted} />
          </span>
          <p className="body-sm text-[color:var(--muted)] mt-3">
            Most recent round with official classification.
          </p>
        </div>
      </div>

      {/* Hairline-divided round list */}
      <div className="hairline-divider-top">
        {calendar.map((r) => {
          const isNext = r.round === nextRound;
          const leftBorder = r.completed
            ? "var(--success)"
            : isNext
            ? "var(--accent)"
            : "var(--hairline-strong)";
          return (
            <Link
              key={r.round}
              href={`/race/${r.round}`}
              className="row-spec flex items-center gap-6 group transition-colors hover:bg-[color:var(--surface-card)] border-l-2"
              style={{ borderLeftColor: "transparent" }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderLeftColor = leftBorder;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderLeftColor = "transparent";
              }}
            >
              <div className="text-center shrink-0 w-12 pl-3">
                <span className="font-mono tabular-nums text-[20px] tracking-[0.05em] text-[color:var(--muted)]">
                  {String(r.round).padStart(2, "0")}
                </span>
              </div>

              <div className="flex items-center gap-3 flex-1 min-w-0">
                <CountryFlag country={r.country} size={32} className="shrink-0" />
                <div className="min-w-0">
                  <div className="flex items-center gap-3 flex-wrap mb-1">
                    <h3 className="title-md truncate group-hover:text-[color:var(--ink)] transition-colors">
                      {r.name}
                    </h3>
                    {r.completed ? (
                      <Badge variant="positive">Completed</Badge>
                    ) : isNext ? (
                      <Badge variant="live">Next up</Badge>
                    ) : (
                      <Badge variant="muted">Upcoming</Badge>
                    )}
                  </div>
                  <p className="eyebrow truncate">
                    {[r.country, formatRallyDate(r.date)].filter(Boolean).join(" · ")}
                  </p>
                </div>
              </div>

              <span
                className="surface-chip hidden sm:inline-flex shrink-0"
                data-surface={r.surface}
                style={{ "--surface-color": r.surfaceColor } as React.CSSProperties}
              >
                {surfaceLabel(r.surface)}
              </span>

              <span
                className="text-[color:var(--muted)] shrink-0 group-hover:text-[color:var(--ink)] transition-colors pr-2"
                aria-hidden
              >
                →
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
