"use client";

/**
 * TitleRaceModule — surfaces the championship win-probability lanes on the
 * homepage so the season's marquee projection isn't three clicks deep.
 *
 * Reuses the exact <WhoCanWinLanes> component from the Standings page (single
 * source of truth for the title-race lanes) and wraps it in the homepage
 * section rhythm.
 *
 * Doubles as the between-race payload: when the featured GP's qualifying isn't
 * official yet, the model has no genuine race forecast (honest publish gate),
 * so this frames the same lanes as a *season outlook* — never a fabricated
 * race prediction.
 */
import Link from "next/link";
import { motion } from "framer-motion";

import WhoCanWinLanes from "@/components/standings/WhoCanWinLanes";
import { fadeUp } from "@/lib/motion";
import type {
  ChampionshipForecast,
  RaceCalendarEntry,
  StandingsData,
} from "@/types";

interface TitleRaceModuleProps {
  standings: StandingsData;
  forecast: ChampionshipForecast | null;
  /** True once the featured GP's qualifying is official (a real race forecast exists). */
  raceForecastLive: boolean;
  /** The upcoming / featured GP — drives the between-race framing copy. */
  featuredRace: RaceCalendarEntry | null;
}

export default function TitleRaceModule({
  standings,
  forecast,
  raceForecastLive,
  featuredRace,
}: TitleRaceModuleProps) {
  // Nothing to project until the season has produced a forecast — never
  // fabricate a title race out of an empty grid.
  if (!forecast?.wdcForecast?.length) return null;

  return (
    <motion.section
      aria-label="Championship title-race projection"
      className="section-bugatti"
      variants={fadeUp}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.15 }}
    >
      <div className="flex items-baseline justify-between mb-8 gap-4 flex-wrap">
        <div className="max-w-2xl">
          <p className="eyebrow mb-2">Championship Projection</p>
          {!raceForecastLive && (
            <p className="body-sm text-[color:var(--muted)]">
              Qualifying for {featuredRace?.name ?? "the next Grand Prix"} isn&apos;t
              official yet, so there&apos;s no race forecast until the grid is set.
              Here&apos;s how the title race is trending across the rest of the season.
            </p>
          )}
        </div>
        <Link
          href="/standings?tab=wdc"
          className="link-bugatti button-label text-[11px]"
        >
          Full Title Race →
        </Link>
      </div>

      <WhoCanWinLanes standings={standings} forecast={forecast} />
    </motion.section>
  );
}
