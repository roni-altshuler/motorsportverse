"use client";

/**
 * AddToCalendar — RaceIQ F3
 *
 * A self-contained, client-only download button that generates a `.ics`
 * calendar file in the browser (no server, no network) and triggers a
 * download. Safe for the static export — all iCalendar work is done by the
 * pure builders in `@/lib/calendar` and the Blob/anchor dance only runs inside
 * the click handler.
 *
 * Pass a single `race` to download one round (its reversed-grid sprint plus the
 * feature race), or `races` (the full season calendar) to download every round.
 * Both come straight from f3.json's `calendar[*]` entries — the component maps
 * the F3 CalendarRound shape onto the `CalendarRace` the builders expect.
 */

import * as React from "react";
import { Button, type ButtonProps } from "@/components/ui/Button";
import {
  buildRaceIcs,
  buildSeasonIcs,
  icsFilename,
  type CalendarRace,
} from "@/lib/calendar";
import type { CalendarRound } from "@/types/f3";

export interface AddToCalendarProps {
  /** A single round to add. Takes precedence over `races`. */
  race?: CalendarRound;
  /** Full-season calendar; used when `race` is omitted. */
  races?: CalendarRound[];
  /** Season year — stamped into the event UID, name and description. */
  season?: number;
  /** Button label. Defaults to a sensible round/season label. */
  label?: string;
  variant?: ButtonProps["variant"];
  size?: ButtonProps["size"];
  className?: string;
}

/** Map the F3 `CalendarRound` onto the builder's `CalendarRace`. */
function toRace(r: CalendarRound): CalendarRace {
  return {
    round: r.round,
    name: r.name,
    city: r.city,
    country: r.country,
    sprintDate: r.sprintDate,
    featureDate: r.featureDate,
  };
}

function CalendarIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

export default function AddToCalendar({
  race,
  races,
  season,
  label,
  variant = "primary",
  size = "sm",
  className,
}: AddToCalendarProps) {
  const hasSeason = !race && Array.isArray(races) && races.length > 0;
  const disabled = !race && !hasSeason;

  const handleDownload = React.useCallback(() => {
    let ics: string;
    let filename: string;

    if (race) {
      const mapped = toRace(race);
      ics = buildRaceIcs(mapped, { season });
      filename = icsFilename(mapped, season);
    } else if (Array.isArray(races) && races.length > 0) {
      ics = buildSeasonIcs(races.map(toRace), { season });
      filename = icsFilename(undefined, season);
    } else {
      return;
    }

    const blob = new Blob([ics], { type: "text/calendar;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    // Revoke on the next tick so the browser has time to start the download.
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }, [race, races, season]);

  const resolvedLabel =
    label ?? (race ? "Add to calendar" : "Add season to calendar");

  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      className={className}
      onClick={handleDownload}
      disabled={disabled}
      aria-label={
        race
          ? `Add ${race.name} to your calendar`
          : "Add the full Formula 3 season to your calendar"
      }
    >
      <CalendarIcon />
      {resolvedLabel}
    </Button>
  );
}
