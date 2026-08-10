"use client";

import { motion } from "framer-motion";

import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import HUDPanel from "@/components/ui/HUDPanel";
import { surfaceLabel } from "@/lib/surface";
import { useReducedMotion } from "@/lib/useReducedMotion";

interface HUDHeaderProps {
  round: number;
  /** Rally / round name shown as the headline. */
  name: string;
  /** Country string for the flag + meta line. */
  country: string | null;
  /** Whether the round has run (drives the result/upcoming pill). */
  completed: boolean;
  /** gravel | tarmac | snow — WRC's signature variable. */
  surface: string;
  /** Colour for the surface chip (from the data). */
  surfaceColor?: string;
  /** Provenance string from the round payload (e.g. "snapshot"). */
  dataSource?: string | null;
}

/**
 * Telemetry-framed rally header — the WRC analogue of the F1 flagship's
 * HUDHeader. A rally is a single classification (no sprint, no qualifying),
 * so the right-hand strip surfaces the defining variable of world rally: the
 * SURFACE the round is run on.
 */
export default function HUDHeader({
  round,
  name,
  country,
  completed,
  surface,
  surfaceColor,
  dataSource,
}: HUDHeaderProps) {
  const reduced = useReducedMotion();

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
            <span
              className="surface-chip"
              data-surface={surface}
              style={surfaceColor ? ({ "--surface-color": surfaceColor } as React.CSSProperties) : undefined}
            >
              {surfaceLabel(surface)}
            </span>
            <Badge variant={completed ? "positive" : "live"}>
              {completed ? "Result + Forecast" : "Upcoming Forecast"}
            </Badge>
          </div>
        }
      >
        <div className="-mx-5 grid grid-cols-1 gap-0 px-5 sm:-mx-6 sm:px-6 md:grid-cols-3">
          <div className="row-spec md:border-b-0 md:pr-6">
            <p className="eyebrow mb-2">Rally</p>
            <p className="title-md">{name}</p>
            {country && (
              <p className="body-sm mt-2 font-mono text-[color:var(--muted)]">{country}</p>
            )}
          </div>
          <div className="row-spec md:border-b-0 md:px-6">
            <p className="eyebrow mb-2">Surface</p>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="surface-chip"
                data-surface={surface}
                style={surfaceColor ? ({ "--surface-color": surfaceColor } as React.CSSProperties) : undefined}
              >
                {surfaceLabel(surface)}
              </span>
            </div>
            <p className="body-sm mt-2 text-[color:var(--muted)]">
              One rally classification each round.
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
