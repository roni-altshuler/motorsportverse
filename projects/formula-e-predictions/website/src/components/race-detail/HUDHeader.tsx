"use client";

import { motion } from "framer-motion";

import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import HUDPanel from "@/components/ui/HUDPanel";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { VenueKind } from "@/types/fe";

interface HUDHeaderProps {
  round: number;
  /** Venue / round name shown as the headline (e.g. "Jeddah II"). */
  name: string;
  /** Country string for the flag + meta line. */
  country: string | null;
  /** Whether the round has run (drives the live/upcoming pill). */
  completed: boolean;
  /** Street E-Prix vs permanent circuit — surfaced as the format indicator. */
  venueKind: VenueKind;
  /** Doubleheader context when this venue hosts two rounds back-to-back. */
  doubleheader?: { race: number; of: number } | null;
  /** Provenance string from the round payload (e.g. "snapshot", "pulselive"). */
  dataSource?: string | null;
}

/**
 * Telemetry-framed race header — the Formula E analogue of the F1 flagship's
 * HUDHeader, adapted to FE's single-race weekends. FE ships no per-round
 * weather, so the right-hand strip carries the venue-kind badge (street vs
 * permanent circuit) and, for doubleheaders, which race of the weekend this is.
 */
export default function HUDHeader({
  round,
  name,
  country,
  completed,
  venueKind,
  doubleheader = null,
  dataSource,
}: HUDHeaderProps) {
  const reduced = useReducedMotion();
  const kindLabel = venueKind === "street" ? "Street Circuit" : "Permanent Circuit";

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
            <span>{name}</span>
          </span>
        }
        rightSlot={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Badge variant="info">{kindLabel}</Badge>
            {doubleheader && (
              <Badge variant="default">
                Doubleheader · Race {doubleheader.race} of {doubleheader.of}
              </Badge>
            )}
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
            <p className="eyebrow mb-2">Weekend Format</p>
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
              {doubleheader
                ? `One scored race — the ${
                    doubleheader.race === 1 ? "first" : "second"
                  } of two at this venue.`
                : "One scored race this weekend."}
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
