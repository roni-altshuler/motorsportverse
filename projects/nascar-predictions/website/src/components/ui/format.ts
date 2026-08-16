/**
 * Shared formatters — one place a number becomes a string.
 *
 * The rule this file exists to enforce: **absent data renders as absent.**
 * `—`, never `0`. "No prediction published" and "predicted last" are different
 * facts, and a UI that draws them identically is lying about one of them. Every
 * function here returns the em dash for null/undefined/NaN rather than
 * coercing, and `formatters.test.ts` asserts it.
 *
 * Synced across every series site by `scripts/sync_shared_ui.mjs` — edit the
 * canonical copy under `projects/f1-predictions/website/src/components/ui/`.
 */

/** The single absent-value glyph. Nothing else may stand in for missing data. */
export const ABSENT = "—";

function missing(value: number | null | undefined): boolean {
  return value === null || value === undefined || Number.isNaN(value);
}

/**
 * A probability as text.
 *
 * **Never colour-only.** Every probability rendered on these sites appears as
 * text, because a reader cannot read 63% off a bar and a colour-blind reader
 * cannot read it off a hue.
 */
export function pct(value: number | null | undefined, digits = 1): string {
  if (missing(value)) return ABSENT;
  return `${(value! * 100).toFixed(digits)}%`;
}

/** A plain number at a fixed precision. */
export function num(value: number | null | undefined, digits = 2): string {
  if (missing(value)) return ABSENT;
  return value!.toFixed(digits);
}

/** A signed number, with the sign always shown — a delta reads wrong without it. */
export function signed(value: number | null | undefined, digits = 2): string {
  if (missing(value)) return ABSENT;
  return `${value! >= 0 ? "+" : ""}${value!.toFixed(digits)}`;
}

/** A whole number with thousands separators. */
export function count(value: number | null | undefined): string {
  if (missing(value)) return ABSENT;
  return Math.round(value!).toLocaleString("en-GB");
}

/** Championship points — one decimal, because half-points exist. */
export function points(value: number | null | undefined): string {
  if (missing(value)) return ABSENT;
  return Number.isInteger(value!) ? String(value) : value!.toFixed(1);
}

/**
 * A finishing position as an ordinal.
 *
 * Position 0 is not a position; it is missing data that survived a `|| 0`
 * somewhere upstream, and it renders as absent rather than as "0th".
 */
export function ordinal(value: number | null | undefined): string {
  if (missing(value) || value! < 1) return ABSENT;
  const n = Math.round(value!);
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

/** A UTC timestamp, labelled UTC — these sites serve every timezone at once. */
export function stamp(iso: string | null | undefined): string {
  if (!iso) return ABSENT;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return ABSENT;
  return (
    date.toLocaleString("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "UTC",
    }) + " UTC"
  );
}

/** A race date, without a time — a calendar entry has no meaningful clock. */
export function raceDate(iso: string | null | undefined): string {
  if (!iso) return ABSENT;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return ABSENT;
  return date.toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}
