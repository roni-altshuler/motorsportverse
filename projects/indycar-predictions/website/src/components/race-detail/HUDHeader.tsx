"use client";

import { motion } from "framer-motion";

import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import HUDPanel from "@/components/ui/HUDPanel";
import { trackTypeLabel } from "@/lib/track";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { TrackType } from "@/types/indycar";

interface HUDHeaderProps {
  round: number;
  /** Venue name shown as the headline (e.g. "Indianapolis Motor Speedway"). */
  name: string;
  /** Marketing race title (e.g. "Indianapolis 500"), when the export ships it. */
  raceName?: string | null;
  /** Country string for the flag + meta line. */
  country: string | null;
  /** Whether the round has run (drives the live/upcoming pill). */
  completed: boolean;
  /** IndyCar track archetype — surfaced as the format indicator. */
  trackType: TrackType;
  /** True only for the Indianapolis 500 (33-car field, the crown jewel). */
  isIndy500?: boolean;
  /** Provenance string from the round payload (e.g. "snapshot"). */
  dataSource?: string | null;
}

/**
 * Telemetry-framed race header — the IndyCar analogue of the F1 flagship's
 * HUDHeader, adapted to single-race IndyCar weekends. The right-hand strip
 * carries the track-type badge (oval / road course / street circuit) and the
 * Indy 500 marker on the crown-jewel round.
 */
export default function HUDHeader({
  round,
  name,
  raceName = null,
  country,
  completed,
  trackType,
  isIndy500 = false,
  dataSource,
}: HUDHeaderProps) {
  const reduced = useReducedMotion();
  const kindLabel = trackTypeLabel(trackType);

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="mb-6"
    >
      <HUDPanel
        kicker={`Round ${String(round).padStart(2, "0")}`}
        title={
          <span className="flex items-center gap-3">
            <CountryFlag country={country} size={36} />
            <span>{raceName || name}</span>
          </span>
        }
        rightSlot={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Badge variant="info">{kindLabel}</Badge>
            {isIndy500 && <Badge variant="live">Indy 500</Badge>}
            <Badge variant={completed ? "positive" : "live"}>
              {completed ? "Result + Forecast" : "Upcoming Forecast"}
            </Badge>
          </div>
        }
      >
        <div className="-mx-5 grid grid-cols-1 gap-0 px-5 sm:-mx-6 sm:px-6 md:grid-cols-3">
          <div className="row-spec md:border-b-0 md:pr-6">
            <p className="eyebrow mb-2">Venue</p>
            <p className="title-md">{name}</p>
            {country && (
              <p className="body-sm mt-2 font-mono text-[color:var(--muted)]">{country}</p>
            )}
          </div>
          <div className="row-spec md:border-b-0 md:px-6">
            <p className="eyebrow mb-2">Race Format</p>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[11px] uppercase tracking-[0.16em]"
                style={{ borderColor: "var(--accent)", color: "var(--accent-f1-red-bright)" }}
              >
                <span
                  aria-hidden
                  className="inline-block h-1.5 w-1.5 rounded-full"
                  style={{ background: "var(--accent)" }}
                />
                {kindLabel}
              </span>
            </div>
            <p className="body-sm mt-2 text-[color:var(--muted)]">
              {isIndy500
                ? "The Indianapolis 500 — a 33-car field, one-off entries included."
                : "One points race this weekend."}
            </p>
          </div>
          <div className="row-spec md:border-b-0 md:pl-6">
            <p className="eyebrow mb-2">Status</p>
            <p className="title-md">{completed ? "Classified" : "Scheduled"}</p>
            {dataSource && (
              <p className="eyebrow mt-2 truncate">Source: {dataSource}</p>
            )}
          </div>
        </div>
      </HUDPanel>
    </motion.div>
  );
}
