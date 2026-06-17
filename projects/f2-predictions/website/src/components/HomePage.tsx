/**
 * HomePage — RaceIQ F2 home, ported from the RaceIQ F1 flagship.
 *
 * Server component: reads the build-time F2 dataset with `getF2Data()` and
 * passes plain data into the (mostly client) sections. The marketing scaffold
 * (hero, trust, how-it-works, features, technical credibility, FAQ, final CTA)
 * always renders; the live product proof (race window, predicted podium,
 * championship bento) renders from the same build-time data.
 *
 * Adapted from F1: F2 has no per-round dates, no telemetry / weather / pit
 * strategy, no separate trust-stats JSON, no constructors constellation. Trust
 * numbers are derived from the season accuracy block.
 */
import Link from "next/link";

import { getF2Data, teamColor } from "@/lib/f2data";
import { Badge } from "@/components/ui/Badge";
import { buttonVariants } from "@/components/ui/Button";
import HeroParallax from "@/components/home/HeroParallax";
import PodiumStage from "@/components/home/PodiumStage";
import RaceCardCarousel from "@/components/home/RaceCardCarousel";
import ChampionshipBento from "@/components/home/ChampionshipBento";
import TrustBand from "@/components/marketing/TrustBand";
import HowItWorksDiagram from "@/components/marketing/HowItWorksDiagram";
import FeatureOutcomes from "@/components/marketing/FeatureOutcomes";
import TechnicalCredibility from "@/components/marketing/TechnicalCredibility";
import FAQ from "@/components/marketing/FAQ";
import FinalCTA from "@/components/marketing/FinalCTA";

export default function HomePage() {
  const data = getF2Data();
  const acc = data.seasonAccuracy;
  const next = data.nextPrediction;
  const nextRound =
    data.calendar.find((c) => !c.completed)?.round ?? null;
  const nextCalendarRound = nextRound
    ? data.calendar.find((c) => c.round === nextRound) ?? null
    : null;
  const roundsRemaining = data.totalRounds - data.completedRounds;
  const roundsScored = acc?.roundsScored ?? data.completedRounds;

  // The predicted podium only teases when a next-round forecast exists.
  const podiumEntries =
    next?.race?.slice(0, 3).map((r) => ({
      driver: r.code,
      driverFullName: r.name,
      team: r.team,
      teamColor: teamColor(r.team),
      winProbability: r.pWin * 100,
    })) ?? [];

  return (
    <div>
      <HeroParallax className="min-h-[78vh] flex items-center">
        <div className="mx-auto w-full max-w-6xl px-6 lg:px-10 py-20">
          {/* ── Value proposition ── */}
          <div className="max-w-3xl">
            <p className="eyebrow mb-5">RaceIQ · Formula 2 · {data.season}</p>
            <h1 className="display-xl [font-weight:700] text-balance">
              Formula 2, forecast.
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
