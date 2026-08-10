/**
 * calendar.ts (Formula E)
 *
 * Pure, dependency-free builders for iCalendar (.ics) strings so a fan can add
 * a Formula E E-Prix — or the whole season — to Apple Calendar, Google
 * Calendar, Outlook, etc. Everything here is a pure function of its inputs
 * (plus an injectable `now` for deterministic tests), so it is safe to import
 * from both server and `"use client"` code in a static export.
 *
 * Ported from the RaceIQ F1 flagship, adapted to Formula E's calendar reality:
 * one scored race per round, split-year seasons, and DOUBLEHEADERS (two rounds
 * sharing one venue). The FE export gives a race *date* but no confirmed
 * lights-out *time*, so by default each race is written as an all-day VEVENT on
 * race day (DTSTART;VALUE=DATE). When a real start time is known it can be
 * passed via `startUtc` and a timed, 2-hour UTC event is emitted instead — no
 * time is ever fabricated.
 *
 * Output conforms to RFC 5545: CRLF line endings, 75-octet line folding, TEXT
 * escaping, and stable per-race UIDs (so re-adding updates the existing event
 * instead of duplicating it).
 */

/** Minimal shape of a race, mapped from fe.json `calendar[*]` entries. */
export interface CalendarRace {
  round: number;
  /** e.g. "London" / "London II" */
  name: string;
  /** e.g. "ExCeL" — the FE export carries a city, used as the location. */
  circuit?: string;
  /** ISO date, "YYYY-MM-DD" */
  date: string;
  /** e.g. "United Kingdom" */
  country?: string;
  /** Optional confirmed lights-out time as an ISO instant. */
  startUtc?: string;
}

export interface IcsOptions {
  /** Season end-year, used in the calendar name + event UIDs. */
  season?: number;
  /** Injectable clock for deterministic DTSTAMP (defaults to `new Date()`). */
  now?: Date;
  /** Duration in minutes for timed events (only used when `startUtc` is set). Default 120. */
  timedDurationMinutes?: number;
}

const PRODID = "-//RaceIQ//Formula E Race Calendar//EN";

/** Split-year label, e.g. 2026 -> "2025-26". */
function seasonLabel(season?: number): string {
  if (season == null) return "";
  return `${season - 1}-${String(season).slice(2)}`;
}

/** RFC 5545 TEXT escaping: backslash, semicolon, comma, and newlines. */
function escapeText(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\r\n|\r|\n/g, "\\n");
}

/** "2026-03-08" -> "20260308" (date-only, floating). */
function toIcsDate(isoDate: string): string {
  return isoDate.replace(/-/g, "");
}

/** A Date -> "YYYYMMDDTHHMMSSZ" (UTC). */
function toIcsUtc(d: Date): string {
  const p = (n: number) => n.toString().padStart(2, "0");
  return (
    `${d.getUTCFullYear()}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}` +
    `T${p(d.getUTCHours())}${p(d.getUTCMinutes())}${p(d.getUTCSeconds())}Z`
  );
}

/** Add whole days to an ISO date string, returning ICS date form. */
function addDaysIcs(isoDate: string, days: number): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  const p = (n: number) => n.toString().padStart(2, "0");
  return `${dt.getUTCFullYear()}${p(dt.getUTCMonth() + 1)}${p(dt.getUTCDate())}`;
}

/**
 * Fold a single content line to <=75 octets per RFC 5545 (continuation lines
 * begin with a single space).
 */
function foldLine(line: string): string {
  if (line.length <= 75) return line;
  const chunks: string[] = [];
  let remaining = line;
  chunks.push(remaining.slice(0, 75));
  remaining = remaining.slice(75);
  while (remaining.length > 0) {
    chunks.push(" " + remaining.slice(0, 74));
    remaining = remaining.slice(74);
  }
  return chunks.join("\r\n");
}

function stableUid(race: CalendarRace, season?: number): string {
  const yr = season ?? new Date(race.date).getUTCFullYear();
  return `fe-${yr}-round-${race.round}@raceiq`;
}

/** Build the VEVENT block (array of unfolded content lines) for one race. */
function buildVeventLines(race: CalendarRace, opts: IcsOptions): string[] {
  const now = opts.now ?? new Date();
  const dtstamp = toIcsUtc(now);
  const uid = stableUid(race, opts.season);
  const label = seasonLabel(opts.season);

  const locationParts = [race.circuit, race.country].filter(Boolean);
  const location = locationParts.join(", ");
  const descParts = [
    `Round ${race.round} of the${label ? " " + label : ""} ABB FIA Formula E World Championship.`,
  ];
  if (race.country) descParts.push(`${race.country}.`);
  descParts.push("Predictions, standings & championship forecasts at RaceIQ.");
  const description = descParts.join(" ");

  const lines: string[] = ["BEGIN:VEVENT", `UID:${uid}`, `DTSTAMP:${dtstamp}`];

  if (race.startUtc) {
    const start = new Date(race.startUtc);
    const durMs = (opts.timedDurationMinutes ?? 120) * 60 * 1000;
    const end = new Date(start.getTime() + durMs);
    lines.push(`DTSTART:${toIcsUtc(start)}`);
    lines.push(`DTEND:${toIcsUtc(end)}`);
  } else {
    // All-day event on race day (DTEND is exclusive → next day).
    lines.push(`DTSTART;VALUE=DATE:${toIcsDate(race.date)}`);
    lines.push(`DTEND;VALUE=DATE:${addDaysIcs(race.date, 1)}`);
  }

  lines.push(`SUMMARY:${escapeText(`${race.name} E-Prix — Formula E`)}`);
  if (location) lines.push(`LOCATION:${escapeText(location)}`);
  lines.push(`DESCRIPTION:${escapeText(description)}`);
  lines.push("TRANSP:TRANSPARENT");
  lines.push("END:VEVENT");
  return lines;
}

function wrapCalendar(veventBlocks: string[][], name: string): string {
  const lines: string[] = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    `PRODID:${PRODID}`,
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    `X-WR-CALNAME:${escapeText(name)}`,
  ];
  for (const block of veventBlocks) lines.push(...block);
  lines.push("END:VCALENDAR");
  return lines.map(foldLine).join("\r\n") + "\r\n";
}

/** Build a complete .ics string containing a single race event. */
export function buildRaceIcs(race: CalendarRace, opts: IcsOptions = {}): string {
  const label = seasonLabel(opts.season);
  const name = `${race.name} E-Prix${label ? ` (Formula E ${label})` : " (Formula E)"}`;
  return wrapCalendar([buildVeventLines(race, opts)], name);
}

/** Build a complete .ics string containing every race in the season. */
export function buildSeasonIcs(
  races: CalendarRace[],
  opts: IcsOptions = {},
): string {
  const label = seasonLabel(opts.season);
  const name = `Formula E${label ? ` ${label}` : ""} Season — RaceIQ`;
  const blocks = races.map((r) => buildVeventLines(r, opts));
  return wrapCalendar(blocks, name);
}

/** A safe, descriptive download filename for a race (or season) calendar. */
export function icsFilename(race?: CalendarRace, season?: number): string {
  if (!race) return `formula-e-${season ?? "season"}-calendar.ics`;
  const slug = race.name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
  return `${slug || `round-${race.round}`}-formula-e${season ? `-${season}` : ""}.ics`;
}
