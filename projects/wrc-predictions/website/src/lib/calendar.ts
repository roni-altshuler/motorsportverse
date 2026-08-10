/**
 * calendar.ts — RaceIQ WRC
 *
 * Pure, dependency-free builders for iCalendar (.ics) strings so a fan can add
 * a WRC round — or the whole season — to Apple Calendar, Google Calendar,
 * Outlook, etc. Adapted from the RaceIQ F1 flagship's lib/calendar.ts to WRC's
 * calendar shape: a round is a SINGLE multi-day rally at one location (the
 * export emits one `date`); there is no sprint and no separate qualifying.
 *
 * Everything here is a pure function of its inputs (plus an injectable `now`
 * for deterministic tests), so it is safe to import from both server and
 * `"use client"` code in a static export.
 *
 * The season JSON gives a rally date but no confirmed start time, so each rally
 * is written as an all-day VEVENT on its day (DTSTART;VALUE=DATE). No time is
 * ever fabricated.
 *
 * Output conforms to RFC 5545: CRLF line endings, 75-octet line folding, TEXT
 * escaping, and stable per-round UIDs (so re-adding updates the existing event
 * instead of duplicating it).
 */

/** Minimal shape of a WRC round, matching wrc.json `calendar[*]` entries. */
export interface CalendarRace {
  round: number;
  /** e.g. "Safari Rally Kenya" */
  name: string;
  /** e.g. "Kenya" */
  country?: string | null;
  /** gravel | tarmac | snow. */
  surface?: string;
  /** ISO date, "YYYY-MM-DD" — the rally date. */
  date?: string;
}

export interface IcsOptions {
  /** Season year, used in the calendar name + event UIDs. */
  season?: number;
  /** Injectable clock for deterministic DTSTAMP (defaults to `new Date()`). */
  now?: Date;
}

const PRODID = "-//RaceIQ//WRC Rally Calendar//EN";

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
 * begin with a single space). We fold on character boundaries at a conservative
 * width; ASCII-dominant rally data keeps this well within the octet limit.
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
  const yr =
    season ??
    (race.date ? new Date(race.date).getUTCFullYear() : new Date().getUTCFullYear());
  return `wrc-${yr}-round-${race.round}@raceiq`;
}

/**
 * Build the VEVENT block (an array of unfolded content lines) for one rally —
 * a single all-day event on the rally's date.
 */
function buildVeventBlock(race: CalendarRace, opts: IcsOptions): string[] | null {
  if (!race.date) return null;
  const now = opts.now ?? new Date();
  const dtstamp = toIcsUtc(now);
  const location = race.country ?? "";
  const uid = stableUid(race, opts.season);

  const surfaceBit = race.surface ? ` (${race.surface})` : "";
  const description =
    `Round ${race.round}${opts.season ? ` of the ${opts.season}` : ""} WRC season${surfaceBit}. ` +
    "Predictions & standings at RaceIQ WRC.";

  const lines: string[] = ["BEGIN:VEVENT", `UID:${uid}`, `DTSTAMP:${dtstamp}`];
  // All-day event on the rally day (DTEND is exclusive → next day).
  lines.push(`DTSTART;VALUE=DATE:${toIcsDate(race.date)}`);
  lines.push(`DTEND;VALUE=DATE:${addDaysIcs(race.date, 1)}`);
  lines.push(`SUMMARY:${escapeText(`${race.name} — WRC`)}`);
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

/** Build a complete .ics string containing one rally. */
export function buildRaceIcs(race: CalendarRace, opts: IcsOptions = {}): string {
  const name = `${race.name}${opts.season ? ` (WRC ${opts.season})` : " (WRC)"}`;
  const block = buildVeventBlock(race, opts);
  return wrapCalendar(block ? [block] : [], name);
}

/** Build a complete .ics string containing every round in the season. */
export function buildSeasonIcs(
  races: CalendarRace[],
  opts: IcsOptions = {},
): string {
  const name = `WRC${opts.season ? ` ${opts.season}` : ""} Season — RaceIQ`;
  const blocks = races
    .map((r) => buildVeventBlock(r, opts))
    .filter((b): b is string[] => b != null);
  return wrapCalendar(blocks, name);
}

/** A safe, descriptive download filename for a round (or season) calendar. */
export function icsFilename(race?: CalendarRace, season?: number): string {
  if (!race) return `wrc-${season ?? "season"}-calendar.ics`;
  const slug = race.name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
  return `${slug || `round-${race.round}`}-wrc${season ? `-${season}` : ""}.ics`;
}
