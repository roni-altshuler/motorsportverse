"use client";

import Link from "next/link";
import { useMemo, useRef } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

import type { CalendarRound } from "@/types/fe";
import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import { Spotlight } from "@/components/magicui/spotlight";
import { NeonGradientCard } from "@/components/magicui/neon-gradient-card";
import { getRaceArt } from "@/lib/raceArt";

type Lifecycle = "completed" | "next" | "upcoming";

interface StatusMeta {
  label: string;
  shortLabel: string;
  variant: "live" | "positive" | "negative" | "muted" | "default";
}

const STATUS: Record<Lifecycle, StatusMeta> = {
  completed: { label: "Result in", shortLabel: "Done", variant: "positive" },
  next: { label: "Next up", shortLabel: "Next", variant: "live" },
  upcoming: { label: "Upcoming", shortLabel: "Soon", variant: "muted" },
};

interface RaceCardCarouselProps {
  /** Full Formula E calendar. */
  calendar: CalendarRound[];
  /** Round number of the next (first not-yet-completed) round, if any. */
  nextRound: number | null;
  /**
   *   `featured`     — 3 cards: previous / next / following (default for home).
   *   `full-season`  — every round, horizontally scrollable.
   */
  mode?: "featured" | "full-season";
  className?: string;
}

/**
 * Photographic race-card carousel, ported from RaceIQ F1's RaceCardCarousel.
 * `getRaceArt(round.key)` resolves a verified aerial photo where one exists;
 * venues without one fall back to the styled gradient card (never a wrong
 * image). Status is derived locally from `completed` + the next-round number.
 * Each card links to `/race/<round>`.
 */
export default function RaceCardCarousel({
  calendar,
  nextRound,
  mode = "featured",
  className,
}: RaceCardCarouselProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  const lifecycleOf = (race: CalendarRound): Lifecycle => {
    if (race.completed) return "completed";
    if (nextRound != null && race.round === nextRound) return "next";
    return "upcoming";
  };

  const races = useMemo(() => {
    if (mode === "full-season") return calendar;
    const featuredRound =
      nextRound ?? calendar.find((r) => r.completed)?.round ?? calendar[0]?.round;
    const idx = calendar.findIndex((r) => r.round === featuredRound);
    const prev = idx > 0 ? calendar[idx - 1] : null;
    const next = idx < calendar.length - 1 ? calendar[idx + 1] : null;
    return [prev, calendar[idx], next].filter(Boolean) as CalendarRound[];
  }, [mode, calendar, nextRound]);

  const scroll = (dir: "left" | "right") => {
    const el = scrollerRef.current;
    if (!el) return;
    const delta = Math.round(el.clientWidth * 0.85) * (dir === "left" ? -1 : 1);
    el.scrollBy({ left: delta, behavior: "smooth" });
  };

  const renderCard = (race: CalendarRound) => {
    const lifecycle = lifecycleOf(race);
    const meta = STATUS[lifecycle];
    const isNext = lifecycle === "next";
    const art = getRaceArt(race.key);

    const inner = (
      <Spotlight
        size={320}
        color="rgba(75,72,255,0.14)"
        className="group h-full w-full rounded-[var(--radius-card)]"
      >
        <Link
          href={`/race/${race.round}`}
          className="hover-lift-premium relative block aspect-[16/9] w-full overflow-hidden rounded-[var(--radius-card)] border border-[color:var(--hairline)] bg-[color:var(--surface-card)]"
        >
          {art ? (
            <div
              className="absolute inset-0 transition-transform duration-700 group-hover:scale-[1.04]"
              style={{
                backgroundImage: `url("${art.src}")`,
                backgroundSize: "cover",
                backgroundPosition: "center",
                filter: "brightness(0.55) saturate(1.05)",
              }}
              aria-hidden
            />
          ) : (
            <div
              className="absolute inset-0"
              style={{
                background:
                  "radial-gradient(120% 120% at 80% 0%, color-mix(in srgb, var(--accent) 22%, transparent), transparent 60%), var(--surface-card)",
              }}
              aria-hidden
            />
          )}
          <div
            className="absolute inset-0"
            style={{
              background:
                "linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.30) 55%, rgba(0,0,0,0.92) 100%)",
            }}
            aria-hidden
          />
          <div className="relative z-10 flex h-full w-full flex-col justify-between p-5 sm:p-7">
            <div className="flex items-center gap-2">
              <Badge variant={meta.variant}>{meta.shortLabel}</Badge>
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
                  {meta.label} · {race.kind === "street" ? "Street Circuit" : "Permanent Circuit"}
                </p>
              </div>
              <span className="caption-uppercase shrink-0 text-[10px] text-[color:var(--ink)]">
                View →
              </span>
            </div>
            {art?.credit && (
              <span
                className="absolute bottom-1.5 right-2 text-[8px] tracking-[0.12em] font-mono uppercase text-[color:var(--ink)]/40"
                aria-hidden
              >
                {art.credit}
              </span>
            )}
          </div>
        </Link>
      </Spotlight>
    );

    const isFeaturedNext = mode === "featured" && isNext;
    return (
      <div
        key={race.round}
        className={`snap-start shrink-0 ${
          mode === "full-season"
            ? "w-[88vw] sm:w-[520px] lg:w-[600px]"
            : "w-[88vw] sm:w-[42vw] lg:w-[33vw] max-w-[640px]"
        }`}
      >
        {isFeaturedNext ? (
          <NeonGradientCard
            borderSize={2}
            borderRadius={4}
            neonColors={{ firstColor: "#1E1AF0", secondColor: "#8B89FF" }}
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
