// Small formatting helpers shared across the WEC UI. No dependencies, no fs —
// safe to import from client and server components alike.

/** Format a 0–1 probability as a percentage string, e.g. 0.1618 → "16%". */
export function pct(x: number | null | undefined, digits = 0): string {
  if (x == null || Number.isNaN(x)) return "—";
  return `${(x * 100).toFixed(digits)}%`;
}

/** Ordinal suffix, e.g. 1 → "1st", 22 → "22nd". */
export function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

/** Trim a trailing ".0" from a number that may carry a float suffix. */
export function tidyNum(n: number): string {
  return Number.isInteger(n) ? String(n) : String(Number(n.toFixed(1)));
}

/** Signed integer delta, e.g. +7 / −3 (uses a real minus sign). */
export function signed(n: number): string {
  if (n === 0) return "0";
  return n > 0 ? `+${n}` : `−${Math.abs(n)}`;
}

/** Human month + day from an ISO string; empty when unparseable. */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** A car's driver lineup as a compact string. */
export function lineup(drivers: string[] | undefined): string {
  if (!drivers || drivers.length === 0) return "";
  return drivers.join(" · ");
}

/** Title-case a possibly ALL-CAPS driver name (keeps particles lower). */
export function properName(name: string): string {
  const particles = new Set(["van", "der", "de", "di", "da", "von", "la", "le"]);
  return name
    .split(/\s+/)
    .map((w) => {
      const lower = w.toLowerCase();
      if (particles.has(lower)) return lower;
      // Preserve hyphenated names (Paul-Loup) and keep existing casing sane.
      return lower
        .split("-")
        .map((p) => (p ? p[0].toUpperCase() + p.slice(1) : p))
        .join("-");
    })
    .join(" ");
}
