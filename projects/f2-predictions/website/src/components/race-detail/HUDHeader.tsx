"use client";

import { motion } from "framer-motion";

import CountryFlag from "@/components/CountryFlag";
import { Badge } from "@/components/ui/Badge";
import HUDPanel from "@/components/ui/HUDPanel";
import { useReducedMotion } from "@/lib/useReducedMotion";

interface HUDHeaderProps {
  round: number;
  /** Venue / round name shown as the headline. */
  name: string;
  /** Country string for the flag + meta line. */
  country: string | null;
  /** Whether the round has run (drives the live/upcoming pill). */
  completed: boolean;
  /** Which race tab is active — surfaces in the dual-race indicator. */
  activeRace: "feature" | "sprint";
  /** Provenance string from the round payload (e.g. "synthetic", "fia"). */
  dataSource?: string;
}

/**
 * Telemetry-framed race header — the F2 analogue of the F1 flagship's
 * HUDHeader, adapted to F2's data reality. F2 ships no per-round weather, so
 * the right-hand weather strip is replaced by a dual-race indicator (every F2
 * round scores both a Sprint and a Feature race).
 */
export default function HUDHeader({
  round,
  name,
  country,
  completed,
  activeRace,
  dataSource,
}: HUDHeaderProps) {
  const reduced = useReducedMotion();

  const races: Array<{ key: "feature" | "sprint"; label: string }> = [
    { key: "feature", label: "Feature" },
    { key: "sprint", label: "Sprint" },
  ];

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
            <Badge variant="info">Sprint + Feature</Badge>
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
              {races.map((r) => (
                <span
                  key={r.key}
                  className="inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[11px] uppercase tracking-[0.16em]"
                  style={
                    r.key === activeRace
                      ? {
                          borderColor: "var(--accent)",
                          color: "var(--accent)",
                        }
                      : {
                          borderColor: "var(--hairline)",
                          color: "var(--muted)",
                        }
                  }
                >
                  <span
                    aria-hidden
                    className="inline-block h-1.5 w-1.5 rounded-full"
                    style={{
                      background: r.key === activeRace ? "var(--accent)" : "var(--muted)",
                    }}
                  />
                  {r.label}
                </span>
              ))}
            </div>
            <p className="body-sm mt-2 text-[color:var(--muted)]">
              Two scored races each round.
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
