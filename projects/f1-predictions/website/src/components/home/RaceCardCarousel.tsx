"use client";

import Link from "next/link";
import { useMemo, useRef } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { RaceCalendarEntry, SeasonData } from "@/types";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import { Spotlight } from "@/components/magicui/spotlight";
import { NeonGradientCard } from "@/components/magicui/neon-gradient-card";
import {
  formatDate,
  getCurrentRaceContext,
  getRoundLifecycle,
  getRoundStatusMeta,
} from "@/lib/data";
import { getRaceArt } from "@/lib/raceArt";

const TONE_TO_BADGE_VARIANT = {
  red: "negative",
  green: "positive",
  amber: "live",
  slate: "muted",
} as const;
type StatusTone = keyof typeof TONE_TO_BADGE_VARIANT;

interface RaceCardCarouselProps {
  /** Season calendar to render. Required. */
  season: SeasonData;
  /** Optional roundsWithActual list — drives lifecycle labelling. */
  roundsWithActual?: number[];
  /**
   * Carousel render mode.
   *
   *   `featured`  — 3 cards: previous / current / next (default for home).
   *   `full-season` — every round, horizontally scrollable (default for calendar).
   */
  mode?: "featured" | "full-season";
  className?: string;
}

/**
 * F1.com-style horizontal photographic race card carousel.
 *
 * - Each card is full-bleed background photography keyed by GP slug.
 * - Cards snap to the start of the scroll container on touch/swipe.
 * - The featured-mode middle card is wrapped in NeonGradientCard when live.
 * - Photography source is the per-round track_map for now (placeholder
 *   until the race-art fetch pipeline lands).
 */
export default function RaceCardCarousel({
  season,
  roundsWithActual = [],
  mode = "featured",
  className,
}: RaceCardCarouselProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  const races = useMemo(() => {
    if (mode === "full-season") return season.calendar;
    const ctx = getCurrentRaceContext(season, roundsWithActual);
    const featured =
      ctx.liveRound ??
      ctx.nextRound ??
      ctx.latestPredictionRound ??
      season.calendar[0];
    const idx = season.calendar.findIndex((r) => r.round === featured.round);
    const prev = idx > 0 ? season.calendar[idx - 1] : null;
    const next = idx < season.calendar.length - 1 ? season.calendar[idx + 1] : null;
    return [prev, featured, next].filter(Boolean) as RaceCalendarEntry[];
  }, [mode, season, roundsWithActual]);

  const scroll = (dir: "left" | "right") => {
    const el = scrollerRef.current;
    if (!el) return;
    const delta = Math.round(el.clientWidth * 0.85) * (dir === "left" ? -1 : 1);
    el.scrollBy({ left: delta, behavior: "smooth" });
  };

  const renderCard = (race: RaceCalendarEntry) => {
    const lifecycle = getRoundLifecycle(
      race,
      season.completedRounds.includes(race.round),
      roundsWithActual.includes(race.round),
    );
    const meta = getRoundStatusMeta(lifecycle);
    const variant: "live" | "positive" | "negative" | "muted" | "default" =
      TONE_TO_BADGE_VARIANT[meta.tone as StatusTone] ?? "default";
    const isLive = lifecycle === "live-weekend" || lifecycle === "awaiting-results";
    const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
    const { src: trackImg, credit: photoCredit } = getRaceArt(race.gpKey, race.round, basePath);

    const inner = (
      <Spotlight
        size={320}
        color="rgba(225,6,0,0.10)"
        className="group h-full w-full rounded-[var(--radius-card)]"
      >
        <Link
          href={`/race/${race.round}`}
          className="hover-lift-premium relative block aspect-[16/9] w-full overflow-hidden rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)]"
        >
          <div
            className="absolute inset-0 transition-transform duration-700 group-hover:scale-[1.04]"
            style={{
              backgroundImage: `url("${trackImg}")`,
              backgroundSize: "cover",
              backgroundPosition: "center",
              filter: "brightness(0.55) saturate(1.05)",
            }}
            aria-hidden
          />
          <div
            className="absolute inset-0"
            style={{
              background:
                "linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.30) 55%, rgba(0,0,0,0.92) 100%)",
            }}
            aria-hidden
          />
          {/* content */}
          <div className="relative z-10 flex h-full w-full flex-col justify-between p-5 sm:p-7">
            <div className="flex items-center gap-2">
              <Badge variant={variant}>{meta.shortLabel}</Badge>
              <span className="eyebrow text-[color:var(--ink)]/80">
                R{race.round}
              </span>
            </div>
            <div className="flex items-end justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <CountryFlag country={race.country} size={28} />
                  <span className="eyebrow text-[color:var(--body-strong)]">
                    {race.country}
                  </span>
                </div>
                <h3 className="display-md leading-[1.05] [font-weight:700]">
                  {race.name}
                </h3>
                <p className="caption-uppercase mt-2 text-[10px] tracking-[0.18em] text-[color:var(--body-strong)]">
                  {formatDate(race.date)}
                </p>
              </div>
              <span className="caption-uppercase shrink-0 text-[10px] text-[color:var(--ink)]">
                View →
              </span>
            </div>
            {photoCredit && (
              <span
                className="absolute bottom-1.5 right-2 text-[8px] tracking-[0.12em] font-mono uppercase text-[color:var(--ink)]/40"
                aria-hidden
              >
                {photoCredit}
              </span>
            )}
          </div>
        </Link>
      </Spotlight>
    );

    const isFeaturedLive = mode === "featured" && isLive;
    return (
      <div
        key={race.round}
        className={`snap-start shrink-0 ${
          mode === "full-season"
            ? "w-[88vw] sm:w-[520px] lg:w-[600px]"
            : "w-[88vw] sm:w-[42vw] lg:w-[33vw] max-w-[640px]"
        }`}
      >
        {isFeaturedLive ? (
          <NeonGradientCard
            borderSize={2}
            borderRadius={4}
            neonColors={{ firstColor: "#E10600", secondColor: "#3671C6" }}
          >
            {inner}
          </NeonGradientCard>
        ) : (
          inner
        )}
      </div>
    );
  };

  return (
    <div className={`relative ${className ?? ""}`}>
      {mode === "full-season" && (
        <div className="absolute -top-12 right-0 z-10 hidden gap-2 sm:flex">
          <button
            onClick={() => scroll("left")}
            className="btn-icon-bugatti"
            aria-label="Previous races"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => scroll("right")}
            className="btn-icon-bugatti"
            aria-label="Next races"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
      <div
        ref={scrollerRef}
        className="flex gap-4 lg:gap-6 overflow-x-auto snap-x snap-mandatory px-1 py-2"
        style={{
          scrollbarWidth: "none",
          msOverflowStyle: "none",
        }}
        data-lenis-prevent
      >
        {races.map(renderCard)}
      </div>
    </div>
  );
}
