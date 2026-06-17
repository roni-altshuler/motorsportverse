// Deterministic synthesis of "live ticker" rows from the registry.
//
// There is no real prediction feed under public/data yet, so we generate
// plausible, presentation-only rows (sport + a sample competitor + a
// calibrated-looking probability). Deterministic (seeded by string) so the
// static export is stable across builds and SSR/CSR match.

import type { TickerRow } from "@/components/landing/PredictionTicker";
import type { Project } from "@/types/registry";

// A few representative names per sport — purely illustrative.
const SAMPLE_NAMES: Record<string, string[]> = {
  "Formula 1": ["Verstappen", "Norris", "Leclerc", "Piastri", "Russell", "Hamilton"],
  "Formula 2": ["Hadjar", "Antonelli", "Maloney", "Crawford", "Aron", "Bortoleto"],
  "Formula 3": ["Goethe", "Beganovic", "Mansell", "Tsolov"],
  "Formula E": ["Wehrlein", "Cassidy", "Dennis", "Evans"],
  IndyCar: ["Palou", "O'Ward", "Newgarden", "Dixon"],
  NASCAR: ["Larson", "Hamlin", "Byron", "Bell"],
  MotoGP: ["Bagnaia", "Martin", "Marquez", "Bastianini"],
  WEC: ["#7 Toyota", "#6 Porsche", "#2 Cadillac", "#51 Ferrari"],
  "24h of Le Mans": ["#7 Toyota", "#6 Porsche", "#50 Ferrari"],
  IMSA: ["#7 Acura", "#31 Cadillac", "#25 BMW"],
  WRC: ["Rovanperä", "Evans", "Neuville", "Tänak"],
};

const METRICS = ["WIN", "PODIUM", "POLE", "TOP 5"];

// Tiny deterministic PRNG (mulberry32) seeded from a string.
function hashStr(s: string): number {
  let h = 1779033703 ^ s.length;
  for (let i = 0; i < s.length; i++) {
    h = Math.imul(h ^ s.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return h >>> 0;
}
function rng(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function synthTickerRows(projects: Project[]): TickerRow[] {
  // Prioritize operational projects, then concepts, so live ones lead.
  const order = [...projects].sort((a, b) => {
    const rank = (m: string) =>
      m === "production" ? 0 : m === "experimental" ? 1 : m === "in-development" ? 2 : 3;
    return rank(a.maturity) - rank(b.maturity);
  });

  const rows: TickerRow[] = [];
  for (const p of order) {
    const names = SAMPLE_NAMES[p.sport] ?? [p.sport];
    const live = p.maturity === "production" || p.maturity === "experimental";
    const seedBase = hashStr(p.slug);
    const r = rng(seedBase);
    const count = live ? 4 : 2;
    for (let i = 0; i < count && i < names.length; i++) {
      const prob = Math.round((0.12 + r() * 0.55) * 100);
      const delta = (r() * 6 - 3) * (live ? 1 : 0.5);
      rows.push({
        key: `${p.slug}-${i}`,
        sport: p.sport,
        accent: p.accent || "#e7102f",
        label: names[i],
        metric: `${METRICS[i % METRICS.length]} ${prob}%`,
        delta: Number(delta.toFixed(1)),
        live,
      });
    }
  }
  return rows;
}
