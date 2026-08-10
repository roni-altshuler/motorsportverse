/**
 * calendar.ts — RaceIQ F3
 *
 * Pure, dependency-free builders for iCalendar (.ics) strings so a fan can add
 * an F3 round — or the whole season — to Apple Calendar, Google Calendar,
 * Outlook, etc. Ported from the RaceIQ F1 flagship's lib/calendar.ts and
 * adapted to F3's leaner calendar shape (a round is a reversed-grid sprint plus
 * a feature race at the same circuit; the export gives us `sprintDate` and
 * `featureDate`, not a single race date).
 *
 * Everything here is a pure function of its inputs (plus an injectable `now`
 * for deterministic tests), so it is safe to import from both server and
 * `"use client"` code in a static export.
 *
 * F3's season JSON gives per-session dates but no confirmed lights-out time, so
 * each session is written as an all-day VEVENT on its day (DTSTART;VALUE=DATE).
 * No time is ever fabricated.
 *
 * Output conforms to RFC 5545: CRLF line endings, 75-octet line folding, TEXT
 * escaping, and stable per-round UIDs (so re-adding updates the existing event
 * instead of duplicating it).
 */

/** Minimal shape of an F3 round, matching f3.json `calendar[*]` entries. */
export interface CalendarRace {
  round: number;
  /** e.g. "Australia" / "Spain (Madrid)" */
  name: string;
  /** e.g. "Melbourne" — the host city (F3 shares F1 circuits). */
  city?: string;
  /** e.g. "Australia" */
  country?: string | null;
  /** ISO date, "YYYY-MM-DD" — the reversed-grid sprint. */
  sprintDate?: string;
  /** ISO date, "YYYY-MM-DD" — the merit feature race. */
  featureDate?: string;
}

export interface IcsOptions {
  /** Season year, used in the calendar name + event UIDs. */
  season?: number;
  /** Injectable clock for deterministic DTSTAMP (defaults to `new Date()`). */
  now?: Date;
}

const PRODID = "-//RaceIQ//F3 Race Calendar//EN";

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
 * width; ASCII-dominant race data keeps this well within the octet limit.
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

/** Every dated session on a round (sprint + feature), in calendar order. */
function sessionsFor(
  race: CalendarRace,
): Array<{ kind: "Sprint" | "Feature"; date: string }> {
  const out: Array<{ kind: "Sprint" | "Feature"; date: string }> = [];
  if (race.sprintDate) out.push({ kind: "Sprint", date: race.sprintDate });
  if (race.featureDate) out.push({ kind: "Feature", date: race.featureDate });
  return out;
}

function stableUid(
  race: CalendarRace,
  session: "Sprint" | "Feature",
  season?: number,
): string {
  const yr =
    season ??
    (race.featureDate || race.sprintDate
      ? new Date((race.featureDate || race.sprintDate)!).getUTCFullYear()
      : new Date().getUTCFullYear());
  return `f3-${yr}-round-${race.round}-${session.toLowerCase()}@raceiq`;
}

/**
 * Build the VEVENT blocks (arrays of unfolded content lines) for one round —
 * one all-day event per dated session (reversed-grid sprint + feature race).
 */
function buildVeventBlocks(race: CalendarRace, opts: IcsOptions): string[][] {
  const now = opts.now ?? new Date();
  const dtstamp = toIcsUtc(now);
  const locationParts = [race.city, race.country].filter(Boolean);
  const location = locationParts.join(", ");

  return sessionsFor(race).map(({ kind, date }) => {
    const uid = stableUid(race, kind, opts.season);
    const descParts = [
      `Round ${race.round}${opts.season ? ` of the ${opts.season}` : ""} FIA Formula 3 season — ${kind.toLowerCase()} race.`,
    ];
    descParts.push("Predictions & standings at RaceIQ F3.");
    const description = descParts.join(" ");

    const lines: string[] = ["BEGIN:VEVENT", `UID:${uid}`, `DTSTAMP:${dtstamp}`];
    // All-day event on session day (DTEND is exclusive → next day).
    lines.push(`DTSTART;VALUE=DATE:${toIcsDate(date)}`);
    lines.push(`DTEND;VALUE=DATE:${addDaysIcs(date, 1)}`);
    lines.push(`SUMMARY:${escapeText(`${race.name} ${kind} — F3`)}`);
    if (location) lines.push(`LOCATION:${escapeText(location)}`);
    lines.push(`DESCRIPTION:${escapeText(description)}`);
    lines.push("TRANSP:TRANSPARENT");
    lines.push("END:VEVENT");
    return lines;
  });
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

/** Build a complete .ics string containing one round's sprint + feature. */
export function buildRaceIcs(race: CalendarRace, opts: IcsOptions = {}): string {
  const name = `${race.name}${opts.season ? ` (F3 ${opts.season})` : " (F3)"}`;
  return wrapCalendar(buildVeventBlocks(race, opts), name);
}

/** Build a complete .ics string containing every round in the season. */
export function buildSeasonIcs(
  races: CalendarRace[],
  opts: IcsOptions = {},
): string {
  const name = `FIA Formula 3${opts.season ? ` ${opts.season}` : ""} Season — RaceIQ`;
  const blocks = races.flatMap((r) => buildVeventBlocks(r, opts));
  return wrapCalendar(blocks, name);
}

/** A safe, descriptive download filename for a round (or season) calendar. */
export function icsFilename(race?: CalendarRace, season?: number): string {
  if (!race) return `f3-${season ?? "season"}-calendar.ics`;
  const slug = race.name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
  return `${slug || `round-${race.round}`}-f3${season ? `-${season}` : ""}.ics`;
}
