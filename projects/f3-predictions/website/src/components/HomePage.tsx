/**
 * HomePage — RaceIQ F3 home, ported from the RaceIQ F1 flagship.
 *
 * Server component: reads the build-time F3 dataset with `getF3Data()` and
 * passes plain data into the (mostly client) sections. The marketing scaffold
 * (hero, trust, how-it-works, features, technical credibility, FAQ, final CTA)
 * always renders; the live product proof (race window, predicted podium,
 * latest official result, championship bento, teams constellation) renders from
 * the same build-time data.
 *
 * Adapted from F1: F3 has no per-round dates beyond sprint/feature dates, no
 * telemetry / weather / pit strategy, and no separate trust-stats JSON. Trust
 * numbers are derived from the season accuracy block. F3 is a spec series with
 * no official constructors' championship, so the constellation is framed as the
 * teams that run the grid, not a constructors' title.
 */
import Link from "next/link";

import { getCircuit, getF3Data, getRound } from "@/lib/f3data";
import { teamColor } from "@/lib/teams";
import type { RaceBlock } from "@/types/f3";
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
  const data = getF3Data();
  const acc = data.seasonAccuracy;
  const next = data.nextPrediction;
  const nextGeometry = next ? getCircuit(next.venueKey) : null;
  const nextRound =
    data.calendar.find((c) => !c.completed)?.round ?? null;
  const nextCalendarRound = nextRound
    ? data.calendar.find((c) => c.round === nextRound) ?? null
    : null;
  const roundsRemaining = data.totalRounds - data.completedRounds;
  const roundsScored = acc?.roundsScored ?? data.completedRounds;

  // The predicted podium only teases when a next-round forecast exists — F3's
  // honest analog of F1's qualifying gate (no forecast, no tease).
  const podiumEntries =
    next?.race?.slice(0, 3).map((r) => ({
      driver: r.code,
      driverFullName: r.name,
      team: r.team,
      teamColor: teamColor(r.team),
      winProbability: r.pWin * 100,
    })) ?? [];

  // ── Latest Official Result — most recent completed round's FEATURE race ──
  // Derive in the server component: find the latest completed calendar round,
  // load its detail, map actualResults codes → driver names/teams via the
  // round's own classification first (most authoritative), then the season
  // standings, then the code itself.
  const latestCompleted = [...data.calendar]
    .filter((c) => c.completed)
    .sort((a, b) => b.round - a.round)[0] ?? null;
  const latestRound = latestCompleted ? getRound(latestCompleted.round) : null;

  const nameByCode = new Map<string, { name: string; team: string; teamColor: string; headshotUrl?: string | null }>();
  for (const d of data.driverStandings) {
    nameByCode.set(d.code, {
      name: d.name,
      team: d.team,
      teamColor: d.teamColor || teamColor(d.team),
      headshotUrl: d.headshotUrl ?? null,
    });
  }

  function mapResults(block: RaceBlock | undefined, limit: number): ResultRow[] {
    if (!block?.actualResults?.length) return [];
    // Round classification carries the richest per-driver metadata.
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
          headshotUrl: cls?.headshotUrl ?? fallback?.headshotUrl ?? null,
        } satisfies ResultRow;
      });
  }

  const featureRows = mapResults(latestRound?.feature, 10);
  const sprintRows = mapResults(latestRound?.sprint, 3);

  return (
    <div>
      <HeroParallax className="min-h-[78vh] flex items-center" geometry={nextGeometry}>
        <div className="mx-auto w-full max-w-6xl px-6 lg:px-10 py-20">
          {/* ── Value proposition ── */}
          <div className="max-w-3xl">
            <p className="eyebrow mb-5">RaceIQ · Formula 3 · {data.season}</p>
            <h1 className="display-xl [font-weight:700] text-balance">
              Formula 3, forecast.
            </h1>
            <p className="body-md mt-6 max-w-2xl text-[color:var(--body-strong)]">
              Sprint, feature-race and championship forecasts for the FIA Formula
              2 championship — from a model built for a spec series, where the
              cars are equal so driver skill rules. The sprint runs a reversed
              grid; the feature race is earned on merit. {data.completedRounds} of{" "}
              {data.totalRounds} rounds complete, on the same MotorsportVerse core
              that powers RaceIQ F1.
            </p>
          </div>

          {/* ── Featured round + CTAs ── */}
          {next && nextCalendarRound ? (
            <div className="mt-12 border-t border-[color:var(--hairline)] pt-8">
              <div className="flex flex-wrap items-center gap-4 mb-6">
                <Badge variant="live">Next up</Badge>
                <span className="eyebrow">
                  R{next.round} · Sprint + Feature
                  {nextCalendarRound.featureDate ? (
                    <>
                      {" · "}
                      <HeroCountdown targetDate={nextCalendarRound.featureDate} />
                    </>
                  ) : null}
                </span>
              </div>
              <div className="mb-8">
                <p className="eyebrow mb-2">Next round · Predicted next</p>
                <h2 className="display-md text-balance">{next.venueName}</h2>
                <p className="body-md mt-3 max-w-2xl text-[color:var(--muted)]">
                  {nextCalendarRound.country ?? "Round " + next.round} · two races,
                  modelled separately — reversed-grid sprint and merit feature.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-4">
                <Link
                  href={`/race/${next.round}`}
                  className={buttonVariants({ variant: "primary" })}
                >
                  Next-round prediction →
                </Link>
                <Link href="/standings" className={buttonVariants({ variant: "primary" })}>
                  Standings
                </Link>
                <Link href="/accuracy" className={buttonVariants({ variant: "ghost" })}>
                  Accuracy
                </Link>
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
            From each round&apos;s finishing orders to a probability for every car
            — here is the path each forecast travels before it reaches you.
          </p>
        </div>
        <HowItWorksDiagram variant="scrollstory" />
      </section>

      {/* ── Features as outcomes ── */}
      <FeatureOutcomes />

      {/* ── Race window ── */}
      <section
        aria-labelledby="race-window-heading"
        className="mx-auto max-w-7xl px-6 lg:px-10 pt-12 sm:pt-16"
      >
        <div className="flex items-baseline justify-between mb-6">
          <div>
            <p className="eyebrow mb-1">Race Window</p>
            <h2 id="race-window-heading" className="display-md">
              This round &amp; beyond
            </h2>
          </div>
          <Link href="/calendar" className="link-bugatti button-label text-[11px]">
            Full Season →
          </Link>
        </div>
        <RaceCardCarousel calendar={data.calendar} nextRound={nextRound} mode="featured" />
      </section>

      <div className="mx-auto max-w-6xl px-6 lg:px-10">
        {/* ── Predicted podium — next round ── */}
        {next && podiumEntries.length > 0 && (
          <section aria-labelledby="forecast-heading" className="section-bugatti">
            <div className="flex items-baseline justify-between mb-12">
              <div>
                <p className="eyebrow mb-2">Race Forecast · Next Round</p>
                <h2 id="forecast-heading" className="display-md">
                  Predicted Podium — {next.venueName}
                </h2>
                <p className="body-md mt-4 max-w-2xl text-[color:var(--muted)]">
                  The model&apos;s top three picks for the feature race at round{" "}
                  {next.round}. Projected race winner plus the two drivers most
                  likely to share the rostrum.
                </p>
              </div>
              <Link href={`/race/${next.round}`} className="link-bugatti button-label">
                Full classification
              </Link>
            </div>
            <PodiumStage entries={podiumEntries} immediate />
          </section>
        )}

        {/* ── Latest official result — most recent completed feature race ── */}
        {latestCompleted && featureRows.length >= 3 && (
          <section aria-labelledby="latest-result-heading" className="section-bugatti">
            <div className="flex items-baseline justify-between mb-8">
              <div>
                <p className="eyebrow mb-2">Race Control</p>
                <h2 id="latest-result-heading" className="display-md">
                  Latest Official Result
                </h2>
                <p className="body-md mt-3 text-[color:var(--muted)]">
                  Round {latestCompleted.round} · {latestCompleted.name} feature race
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
            <LatestResult feature={featureRows} sprint={sprintRows} />
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
              teamStandings={data.teamStandings}
              championship={data.championship}
              nextRace={nextCalendarRound}
              roundsRemaining={roundsRemaining}
              totalRounds={data.totalRounds}
              seasonAccuracy={acc}
              roundsCompleted={roundsScored}
            />
          </section>
        )}

        {/* ── Teams constellation ── F3 is a spec series with no official
            constructors' championship, so the copy is about the teams that run
            the grid, not a constructors' title. */}
        {data.teamStandings.length > 0 && (
          <section
            aria-labelledby="constellation-heading"
            className="section-bugatti relative"
          >
            <div className="text-center mb-10">
              <p className="eyebrow mb-2">Constellation</p>
              <h2 id="constellation-heading" className="display-md">
                The teams behind the grid
              </h2>
              <p className="body-md mt-3 max-w-xl mx-auto text-[color:var(--muted)]">
                {data.teamStandings.length} teams run the {data.season} FIA Formula 3
                field — every car on the grid, in orbit. F3 is a spec series, so it
                is the drivers, not the machines, who decide the season.
              </p>
            </div>
            <ConstructorsConstellation
              teams={data.teamStandings}
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
