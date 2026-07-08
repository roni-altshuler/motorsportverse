"use client";

import Link from "next/link";

import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import SeasonRibbon from "@/components/calendar/SeasonRibbon";
import { NumberTicker } from "@/components/magicui/number-ticker";
import { useSeasonFEData } from "@/lib/feclient";
import { getRaceArt } from "@/lib/raceArt";
import type { CalendarRound } from "@/types/fe";

interface CalendarPageProps {
  season: number;
  totalRounds: number;
  completedRounds: number;
  calendar: CalendarRound[];
}

/** Consecutive rounds sharing a venue key form one weekend group. */
interface VenueGroup {
  key: string;
  rounds: CalendarRound[];
}

function groupByVenue(calendar: CalendarRound[]): VenueGroup[] {
  const groups: VenueGroup[] = [];
  for (const r of calendar) {
    const last = groups[groups.length - 1];
    if (last && last.key === r.key) last.rounds.push(r);
    else groups.push({ key: r.key, rounds: [r] });
  }
  return groups;
}

function formatDate(iso: string | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/**
 * Formula E port of the RaceIQ F1 CalendarPage: a SeasonRibbon strip, a
 * photographic race-card grid (aerial circuit art via getRaceArt), a 3-up
 * season-stats row, and a hairline-divided round list. Adapted to Formula E's
 * calendar reality: one scored race per round, a street/circuit venue kind on
 * every round, and DOUBLEHEADERS — two rounds sharing one venue render as a
 * single paired weekend card group ("Jeddah" / "Jeddah II").
 *
 * Multi-season: the page is baked with the CURRENT season's data (static
 * export); when the SeasonSwitcher selects an archived season, that season's
 * fe.json overlays the baked props client-side (mirrors F1's useSeason wiring).
 */
export default function CalendarPage({
  season: baseSeason,
  totalRounds: baseTotalRounds,
  completedRounds: baseCompletedRounds,
  calendar: baseCalendar,
}: CalendarPageProps) {
  const { data: seasonData, isArchived } = useSeasonFEData();
  const overlay = isArchived && seasonData ? seasonData : null;
  const season = overlay?.season ?? baseSeason;
  const totalRounds = overlay?.totalRounds ?? baseTotalRounds;
  const completedRounds = overlay?.completedRounds ?? baseCompletedRounds;
  const calendar = overlay?.calendar ?? baseCalendar;
  const remaining = totalRounds - completedRounds;
  const lastCompleted = calendar.filter((r) => r.completed).reduce((m, r) => Math.max(m, r.round), 0);
  const nextRound = calendar.find((r) => !r.completed)?.round;
  const seasonLabel = `${season - 1}-${String(season).slice(2)}`;
  const groups = groupByVenue(calendar);
  const venues = groups.length;

  const statusChip = (r: CalendarRound, isNext: boolean) => (
    <span
      className="rounded-full px-2 py-0.5 text-[11px] font-medium backdrop-blur"
      style={
        r.completed
          ? {
              color: "var(--muted)",
              background: "color-mix(in srgb, var(--canvas) 60%, transparent)",
            }
          : {
              color: "var(--accent-f1-red-bright)",
              background: "color-mix(in srgb, var(--accent) 22%, transparent)",
            }
      }
    >
      {r.completed ? "Completed" : isNext ? "Next up" : "Upcoming"}
    </span>
  );

  const kindChip = (r: CalendarRound) => (
    <span
      className="rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase tracking-[0.12em] backdrop-blur"
      style={{
        color: "var(--body-strong)",
        borderColor: "color-mix(in srgb, var(--ink) 25%, transparent)",
        background: "color-mix(in srgb, var(--canvas) 55%, transparent)",
      }}
    >
      {r.kind === "street" ? "Street" : "Circuit"}
    </span>
  );

  const renderCard = (r: CalendarRound, opts?: { inPair?: boolean }) => {
    const art = getRaceArt(r.key);
    const isNext = r.round === nextRound;
    const date = formatDate(r.raceDate);
    return (
      <Link
        href={`/race/${r.round}`}
        className="group block overflow-hidden rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] transition-colors hover:border-[color:var(--accent-f1-red-hover)]"
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
                background:
                  "radial-gradient(120% 120% at 80% 0%, color-mix(in srgb, var(--accent) 30%, transparent), transparent 60%), var(--surface-elevated)",
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
          <div className="absolute left-4 top-4 flex flex-wrap items-center gap-2">
            <span className="font-mono rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--canvas)_70%,transparent)] px-2 py-0.5 text-xs font-semibold tracking-[0.14em] text-[color:var(--ink)] backdrop-blur">
              R{r.round}
            </span>
            {statusChip(r, isNext)}
            {!opts?.inPair && kindChip(r)}
          </div>
          <div className="absolute inset-x-4 bottom-3 flex items-center gap-3">
            {!opts?.inPair && <CountryFlag country={r.country} size={28} className="shrink-0" />}
            <div className="min-w-0">
              <p className="font-display text-xl font-bold leading-none text-[color:var(--ink)] truncate">
                {r.name}
              </p>
              <p className="mt-1 text-xs text-[color:var(--muted)]">
                {[date, opts?.inPair ? null : r.country].filter(Boolean).join(" · ")}
              </p>
            </div>
          </div>
        </div>
      </Link>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 section-bugatti">
      <div className="mb-12 max-w-3xl">
        <p className="eyebrow mb-4">Formula E · Season {seasonLabel}</p>
        <h1 className="display-xl [font-weight:700] mb-4">Season Calendar</h1>
        <p className="body-md text-[color:var(--body)] mb-2">
          Every E-Prix of the {seasonLabel} season — a forecast before each race, the
          official result after. One scored race per round; doubleheader weekends run
          two rounds back-to-back at the same venue.
        </p>
        <p className="body-sm text-[color:var(--muted)]">
          {totalRounds} rounds across {venues} venues · {completedRounds} complete ·{" "}
          {remaining} remaining
        </p>
      </div>

      <SeasonRibbon calendar={calendar} />

      {/* Photographic race-card grid — doubleheaders pair up under one venue header */}
      <section className="mb-16" aria-labelledby="season-window-heading">
        <div className="flex items-baseline justify-between mb-6">
          <div>
            <p className="eyebrow mb-1">Season Window</p>
            <h2 id="season-window-heading" className="display-md">
              {totalRounds} rounds, {venues} venues
            </h2>
          </div>
        </div>
        <ol className="grid gap-6 sm:grid-cols-2">
          {groups.map((g) => {
            const first = g.rounds[0];
            if (g.rounds.length === 1) {
              return <li key={g.key + first.round}>{renderCard(first)}</li>;
            }
            // Doubleheader — one venue card group holding both rounds.
            return (
              <li key={g.key + first.round} className="sm:col-span-2">
                <div className="rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-soft)] p-3 sm:p-4">
                  <div className="mb-3 flex flex-wrap items-center gap-3 px-1">
                    <CountryFlag country={first.country} size={24} className="shrink-0" />
                    <p className="title-sm text-[color:var(--ink)]">
                      {first.name.replace(/\s+II$/, "")}
                    </p>
                    <Badge variant="info">Doubleheader</Badge>
                    {kindChip(first)}
                    <span className="body-sm text-[color:var(--muted)]">
                      R{g.rounds[0].round} + R{g.rounds[g.rounds.length - 1].round} · two
                      races, one weekend
                    </span>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {g.rounds.map((r) => (
                      <div key={r.round}>{renderCard(r, { inPair: true })}</div>
                    ))}
                  </div>
                </div>
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
          <span className="display-xl !text-[64px] !leading-none [font-weight:700] text-[color:var(--accent-f1-red-bright)]">
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
          const date = formatDate(r.raceDate);
          const leftBorder = r.completed
            ? "var(--success)"
            : isNext
            ? "var(--accent-f1-red-hover)"
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
                    <Badge variant="muted">{r.kind === "street" ? "Street" : "Circuit"}</Badge>
                    {r.completed ? (
                      <Badge variant="positive">Completed</Badge>
                    ) : isNext ? (
                      <Badge variant="live">Next up</Badge>
                    ) : (
                      <Badge variant="muted">Upcoming</Badge>
                    )}
                  </div>
                  <p className="eyebrow truncate">
                    {[date, r.country].filter(Boolean).join(" · ")}
                  </p>
                </div>
              </div>

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
