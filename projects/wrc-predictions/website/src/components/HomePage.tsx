/**
 * HomePage — RaceIQ WRC home, ported from the RaceIQ F1 flagship.
 *
 * Server component: reads the build-time WRC dataset with `getWrcData()` and
 * passes plain data into the (mostly client) sections. The marketing scaffold
 * (hero, trust, how-it-works, features, technical credibility, FAQ, final CTA)
 * always renders; the live product proof (rally window, predicted podium,
 * latest official result, championship bento, manufacturers constellation)
 * renders from the same build-time data.
 *
 * Adapted from F1: a WRC round is a SINGLE rally classification (one result per
 * round — no short-format stage, no time-trial seeding, no starting order and no
 * fixed-course map), run over public special stages. The rally's surface —
 * gravel, tarmac or snow — is WRC's signature
 * variable and is surfaced prominently. WRC runs both a drivers' (crew) and a
 * manufacturers' world championship (Toyota, Hyundai, M-Sport Ford, …), so the
 * constellation is the manufacturers behind the Rally1 field.
 */
import Link from "next/link";

import { getWrcData, getRound } from "@/lib/wrcData";
import { teamColor } from "@/lib/teams";
import { surfaceColor, surfaceLabel } from "@/lib/surface";
import type { RallyBlock } from "@/types/wrc";
import AddToCalendar from "@/components/AddToCalendar";
import { Badge } from "@/components/ui/Badge";
import { buttonVariants } from "@/components/ui/Button";
import HeroParallax from "@/components/home/HeroParallax";
import HeroCountdown from "@/components/home/HeroCountdown";
import PodiumStage from "@/components/home/PodiumStage";
import RaceCardCarousel from "@/components/home/RaceCardCarousel";
import ChampionshipBento from "@/components/home/ChampionshipBento";
import ConstructorsConstellation from "@/components/home/ConstructorsConstellation";
import LatestResult, { type ResultRow } from "@/components/home/LatestResult";
import TrustBand from "@/components/marketing/TrustBand";
import HowItWorksDiagram from "@/components/marketing/HowItWorksDiagram";
import FeatureOutcomes from "@/components/marketing/FeatureOutcomes";
import TechnicalCredibility from "@/components/marketing/TechnicalCredibility";
import FAQ from "@/components/marketing/FAQ";
import FinalCTA from "@/components/marketing/FinalCTA";

export default function HomePage() {
  const data = getWrcData();
  const acc = data.seasonAccuracy;
  const next = data.nextPrediction;
  const nextRound =
    data.calendar.find((c) => !c.completed)?.round ?? null;
  const nextCalendarRound = nextRound
    ? data.calendar.find((c) => c.round === nextRound) ?? null
    : null;
  const roundsRemaining = data.totalRounds - data.completedRounds;
  const roundsScored = acc?.roundsScored ?? data.completedRounds;

  // The predicted podium only teases when a next-rally forecast exists — WRC's
  // honest analog of F1's pre-session gate (no forecast, no tease).
  const podiumEntries =
    next?.rally?.slice(0, 3).map((r) => ({
      driver: r.code,
      driverFullName: r.name,
      team: r.team,
      teamColor: teamColor(r.team),
      winProbability: r.pWin * 100,
    })) ?? [];

  // ── Latest Official Result — most recent completed round's rally ──
  // Derive in the server component: find the latest completed calendar round,
  // load its detail, map actualResults codes → crew names/teams via the round's
  // own classification first (most authoritative), then the season standings,
  // then the code itself.
  const latestCompleted = [...data.calendar]
    .filter((c) => c.completed)
    .sort((a, b) => b.round - a.round)[0] ?? null;
  const latestRound = latestCompleted ? getRound(latestCompleted.round) : null;

  const nameByCode = new Map<string, { name: string; team: string; teamColor: string }>();
  for (const d of data.driverStandings) {
    nameByCode.set(d.code, {
      name: d.name,
      team: d.team,
      teamColor: d.teamColor || teamColor(d.team),
    });
  }

  function mapResults(block: RallyBlock | undefined, limit: number): ResultRow[] {
    if (!block?.actualResults?.length) return [];
    // Round classification carries the richest per-crew metadata.
    const byCode = new Map(
      (block.classification ?? []).map((c) => [c.code, c] as const),
    );
    return [...block.actualResults]
      .sort((a, b) => a.position - b.position)
      .slice(0, limit)
      .map((res) => {
        const cls = byCode.get(res.code);
        const fallback = nameByCode.get(res.code);
        const team = cls?.team ?? fallback?.team ?? "—";
        const tc = cls?.teamColor ?? fallback?.teamColor ?? teamColor(team);
        return {
          position: res.position,
          code: res.code,
          name: cls?.name ?? fallback?.name ?? res.code,
          team,
          teamColor: tc,
        } satisfies ResultRow;
      });
  }

  const rallyRows = mapResults(latestRound?.rally, 10);

  const heroSurface = next?.surface ?? nextCalendarRound?.surface ?? null;
  const heroSurfaceColor =
    next?.surfaceColor ?? nextCalendarRound?.surfaceColor ?? null;

  return (
    <div>
      <HeroParallax
        className="min-h-[78vh] flex items-center"
        surface={heroSurface}
        surfaceColor={heroSurfaceColor}
      >
        <div className="mx-auto w-full max-w-6xl px-6 lg:px-10 py-20">
          {/* ── Value proposition ── */}
          <div className="max-w-3xl">
            <p className="eyebrow mb-5">RaceIQ · WRC · {data.season}</p>
            <h1 className="display-xl [font-weight:700] text-balance">
              World Rally Championship, forecast.
            </h1>
            <p className="body-md mt-6 max-w-2xl text-[color:var(--body-strong)]">
              Rally and championship forecasts for the FIA World Rally
              Championship — a win and podium probability for every crew, and the
              drivers&apos; and manufacturers&apos; title fights projected to the
              final round. Every rally is scored on its surface — gravel, tarmac
              or snow, the single biggest driver of who is fast.{" "}
              {data.completedRounds} of {data.totalRounds} rounds complete, on the
              same MotorsportVerse core that powers RaceIQ F1.
            </p>
          </div>

          {/* ── Featured round + CTAs ── */}
          {next && nextCalendarRound ? (
            <div className="mt-12 border-t border-[color:var(--hairline)] pt-8">
              <div className="flex flex-wrap items-center gap-4 mb-6">
                <Badge variant="live">Next up</Badge>
                <span
                  className="surface-chip"
                  data-surface={next.surface}
                  style={
                    {
                      "--surface-color": surfaceColor(
                        next.surface,
                        next.surfaceColor,
                      ),
                    } as React.CSSProperties
                  }
                >
                  {surfaceLabel(next.surface)}
                </span>
                <span className="eyebrow">
                  R{next.round} · Rally
                  {nextCalendarRound.date ? (
                    <>
                      {" · "}
                      <HeroCountdown targetDate={nextCalendarRound.date} />
                    </>
                  ) : null}
                </span>
              </div>
              <div className="mb-8">
                <p className="eyebrow mb-2">Next round · Predicted</p>
                <h2 className="display-md text-balance">{next.venueName}</h2>
                <p className="body-md mt-3 max-w-2xl text-[color:var(--muted)]">
                  {nextCalendarRound.country ?? "Round " + next.round} · one
                  classification, every crew ranked across the rally&apos;s special
                  stages on {surfaceLabel(next.surface).toLowerCase()}.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-4">
                <Link
                  href={`/race/${next.round}`}
                  className={buttonVariants({ variant: "primary" })}
                >
                  Next-rally prediction →
                </Link>
                <Link href="/standings" className={buttonVariants({ variant: "primary" })}>
                  Standings
                </Link>
                <Link href="/accuracy" className={buttonVariants({ variant: "ghost" })}>
                  Accuracy
                </Link>
                <AddToCalendar
                  race={nextCalendarRound}
                  season={data.season}
                  variant="ghost"
                  size="md"
                  label="Add to calendar"
                />
              </div>
            </div>
          ) : (
            <div className="mt-12 border-t border-[color:var(--hairline)] pt-8 flex flex-wrap items-center gap-4">
              <Link href="/standings" className={buttonVariants({ variant: "primary" })}>
                Standings
              </Link>
              <Link href="/accuracy" className={buttonVariants({ variant: "ghost" })}>
                Accuracy
              </Link>
            </div>
          )}
        </div>
      </HeroParallax>

      {/* ── Trust band ── */}
      <TrustBand
        roundsScored={roundsScored}
        totalRounds={data.totalRounds}
        podiumHitRate={acc?.podiumHitRate ?? null}
        winnerHitRate={acc?.winnerHitRate ?? null}
        meanPositionError={acc?.meanPositionError ?? null}
        generatedAt={data.generatedAt ?? null}
      />

      {/* ── How it works — sticky scroll-story ── */}
      <section
        aria-labelledby="how-heading"
        className="mx-auto max-w-7xl px-6 lg:px-10 section-bugatti"
      >
        <div className="mb-12 max-w-2xl">
          <p className="eyebrow mb-2">How it works</p>
          <h2 id="how-heading" className="display-md">
            Results → model → forecast
          </h2>
          <p className="body-md mt-4 text-[color:var(--body)]">
            From each rally&apos;s finishing order to a probability for every crew
            — here is the path each forecast travels before it reaches you.
          </p>
        </div>
        <HowItWorksDiagram variant="scrollstory" />
      </section>

      {/* ── Features as outcomes ── */}
      <FeatureOutcomes />

      {/* ── Rally window ── */}
      <section
        aria-labelledby="race-window-heading"
        className="mx-auto max-w-7xl px-6 lg:px-10 pt-12 sm:pt-16"
      >
        <div className="flex items-baseline justify-between mb-6">
          <div>
            <p className="eyebrow mb-1">Rally Window</p>
            <h2 id="race-window-heading" className="display-md">
              This rally &amp; beyond
            </h2>
          </div>
          <Link href="/calendar" className="link-bugatti button-label text-[11px]">
            Full Season →
          </Link>
        </div>
        <RaceCardCarousel calendar={data.calendar} nextRound={nextRound} mode="featured" />
      </section>

      <div className="mx-auto max-w-6xl px-6 lg:px-10">
        {/* ── Predicted podium — next rally ── */}
        {next && podiumEntries.length > 0 && (
          <section aria-labelledby="forecast-heading" className="section-bugatti">
            <div className="flex items-baseline justify-between mb-12">
              <div>
                <p className="eyebrow mb-2">Rally Forecast · Next Round</p>
                <h2 id="forecast-heading" className="display-md">
                  Predicted Podium — {next.venueName}
                </h2>
                <p className="body-md mt-4 max-w-2xl text-[color:var(--muted)]">
                  The model&apos;s top three picks for the rally at round{" "}
                  {next.round}. Projected rally winner plus the two crews most
                  likely to join them on the podium.
                </p>
              </div>
              <Link href={`/race/${next.round}`} className="link-bugatti button-label">
                Full classification
              </Link>
            </div>
            <PodiumStage entries={podiumEntries} immediate />
          </section>
        )}

        {/* ── Latest official result — most recent completed rally ── */}
        {latestCompleted && rallyRows.length >= 3 && (
          <section aria-labelledby="latest-result-heading" className="section-bugatti">
            <div className="flex items-baseline justify-between mb-8">
              <div>
                <p className="eyebrow mb-2">Rally Control</p>
                <h2 id="latest-result-heading" className="display-md">
                  Latest Official Result
                </h2>
                <p className="body-md mt-3 text-[color:var(--muted)]">
                  Round {latestCompleted.round} · {latestCompleted.name}
                  {latestCompleted.country ? ` · ${latestCompleted.country}` : ""}
                </p>
              </div>
              <Link
                href={`/race/${latestCompleted.round}`}
                className="link-bugatti button-label"
              >
                Compare to prediction
              </Link>
            </div>
            <LatestResult results={rallyRows} />
          </section>
        )}

        {/* ── Championship snapshot ── */}
        {data.driverStandings.length > 0 && (
          <section aria-labelledby="championship-heading" className="section-bugatti">
            <div className="flex items-baseline justify-between mb-10">
              <div>
                <p className="eyebrow mb-2">Championship Snapshot</p>
                <h2 id="championship-heading" className="display-md">
                  Where the season stands
                </h2>
              </div>
              <Link href="/standings" className="link-bugatti button-label text-[11px]">
                Open Standings →
              </Link>
            </div>
            <ChampionshipBento
              driverStandings={data.driverStandings}
              manufacturerStandings={data.manufacturerStandings}
              championship={data.championship}
              nextRace={nextCalendarRound}
              roundsRemaining={roundsRemaining}
              totalRounds={data.totalRounds}
              seasonAccuracy={acc}
              roundsCompleted={roundsScored}
            />
          </section>
        )}

        {/* ── Manufacturers constellation ── WRC runs a manufacturers' world
            championship alongside the crews' title, so the copy is about the
            marques that build the Rally1 cars. */}
        {data.manufacturerStandings.length > 0 && (
          <section
            aria-labelledby="constellation-heading"
            className="section-bugatti relative"
          >
            <div className="text-center mb-10">
              <p className="eyebrow mb-2">Constellation</p>
              <h2 id="constellation-heading" className="display-md">
                The manufacturers behind the field
              </h2>
              <p className="body-md mt-3 max-w-xl mx-auto text-[color:var(--muted)]">
                The {data.manufacturerStandings.length} manufacturer entries in the{" "}
                {data.season} World Rally Championship — Toyota, Hyundai and
                M-Sport Ford at the front of the Rally1 field — each chasing a
                manufacturers&apos; world title alongside the crews.
              </p>
            </div>
            <ConstructorsConstellation
              teams={data.manufacturerStandings}
              seasonYear={data.season}
            />
          </section>
        )}
      </div>

      {/* ── Technical credibility ── */}
      <TechnicalCredibility
        generatedAt={data.generatedAt ?? null}
        roundsGraded={roundsScored}
      />

      {/* ── FAQ ── */}
      <FAQ />

      {/* ── Final CTA ── */}
      <FinalCTA />
    </div>
  );
}
