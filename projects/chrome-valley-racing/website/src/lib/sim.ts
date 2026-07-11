// Client-side port of chrome_valley/simulate.py (simplified single-race form).
// Pure TypeScript + a tiny seeded PRNG — runs entirely in the browser, no fs,
// no network. Personality is the physics engine, same knobs as the Python sim:
// pace sets the lap time, consistency shrinks noise, grit shrugs off chaos,
// heart surges in the final quarter, and showboats crash while leading late.

import type { CharacterCard, VenueCard } from "@/types/data";

// ── Tuning knobs (mirrors simulate.py) ────────────────────────────────
const BASE_LAP = 60.0;
const PACE_SECONDS = 0.03;
const NOISE_FLOOR = 0.25;
const NOISE_PER_INCONSISTENCY = 1.1;
const CHAOS_GRIT_PENALTY = 0.85;
const HEART_LATE_SECONDS = 0.5;
const LATE_PHASE = 0.75;
const FINAL_THIRD = 2 / 3;
const SHOWBOAT_CRASH_COEFF = 0.35;
const PIT_STOP_SECONDS = 22.0;
const PIT_MISHAP_COEFF = 0.6;
const MECHANICAL_COEFF = 0.035;

// ── Seeded PRNG (mulberry32) + gaussian ───────────────────────────────
export type Rng = () => number;

export function mulberry32(seed: number): Rng {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gauss(rng: Rng, mean = 0, sd = 1): number {
  // Box-Muller.
  let u = 0;
  let v = 0;
  while (u === 0) u = rng();
  while (v === 0) v = rng();
  return mean + sd * Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

// ── Result shapes ──────────────────────────────────────────────────────
export type FeedTone = "info" | "drama" | "heart" | "finish";

export interface FeedEvent {
  lap: number;
  laps: number;
  tone: FeedTone;
  text: string;
}

export interface SimResult {
  position: number;
  slug: string;
  name: string;
  number: number;
  color: string;
  dnf: boolean;
  dnfReason: string | null;
  gapSeconds: number | null;
  lapsLed: number;
}

export interface SimRace {
  events: FeedEvent[];
  results: SimResult[];
}

function effectivePace(char: CharacterCard, venue: VenueCard): number {
  let pace = char.basePace;
  for (const [tag, bonus] of Object.entries(char.affinity)) {
    if (venue.tags.includes(tag)) pace += bonus;
  }
  return pace;
}

// ── The race ───────────────────────────────────────────────────────────
export function simulateRace(
  characters: CharacterCard[],
  venue: VenueCard,
  seed: number,
  withFeed = true
): SimRace {
  const rng = mulberry32(seed);
  const laps = venue.laps;
  const pitLap = Math.max(2, Math.floor(laps * 0.55));
  const lateStart = Math.floor(laps * LATE_PHASE);
  const finalThirdStart = Math.floor(laps * FINAL_THIRD);
  const finalThirdLaps = laps - finalThirdStart;

  const total = new Map<string, number>();
  const retired = new Set<string>();
  const dnfLap = new Map<string, number>();
  const dnfReason = new Map<string, string>();
  const lapsLed = new Map<string, number>();
  const events: FeedEvent[] = [];
  let finalThirdOrder: string[] = [];

  const bySlug = new Map(characters.map((c) => [c.slug, c]));
  const push = (lap: number, tone: FeedTone, text: string) => {
    if (withFeed) events.push({ lap, laps, tone, text });
  };

  for (const c of characters) {
    total.set(c.slug, 0);
    lapsLed.set(c.slug, 0);
    const pMech = MECHANICAL_COEFF * (0.5 + venue.chaos) * Math.max(0, 1.1 - c.traits.grit / 100);
    if (rng() < pMech) {
      dnfLap.set(c.slug, 3 + Math.floor(rng() * (laps - 5)));
      dnfReason.set(c.slug, "mechanical gremlins");
    }
  }

  push(0, "info", `Green flag at ${venue.name} — ${laps} laps of ${venue.kind.toLowerCase()}.`);

  const runningOrder = () =>
    characters
      .filter((c) => !retired.has(c.slug))
      .map((c) => c.slug)
      .sort((a, b) => (total.get(a) ?? 0) - (total.get(b) ?? 0));

  let leader: string | null = null;
  const quarter = Math.max(1, Math.floor(laps / 4));

  for (let lap = 1; lap <= laps; lap++) {
    for (const c of characters) {
      const slug = c.slug;
      if (retired.has(slug)) continue;
      if (dnfReason.get(slug) === "mechanical gremlins" && dnfLap.get(slug) === lap) {
        retired.add(slug);
        push(lap, "drama", `${c.name} coasts to a stop — mechanical gremlins. The tow rope is out.`);
        continue;
      }
      let lapTime = BASE_LAP - effectivePace(c, venue) * PACE_SECONDS;
      lapTime += gauss(rng, 0, NOISE_FLOOR + ((100 - c.traits.consistency) / 100) * NOISE_PER_INCONSISTENCY);
      lapTime += venue.chaos * ((100 - c.traits.grit) / 100) * CHAOS_GRIT_PENALTY * Math.abs(gauss(rng, 0, 0.8));
      if (lap > lateStart) lapTime -= (HEART_LATE_SECONDS * c.traits.heart) / 100;
      if (lap === pitLap) {
        lapTime += PIT_STOP_SECONDS;
        if (rng() < venue.pitDrama * (1 - c.traits.consistency / 100) * PIT_MISHAP_COEFF) {
          const loss = 4 + rng() * 8;
          lapTime += loss;
          push(lap, "drama", `${c.name}'s pit stop goes sideways — a fumbled tire costs ${loss.toFixed(0)} seconds.`);
        }
      }
      total.set(slug, (total.get(slug) ?? 0) + lapTime);
    }

    const order = runningOrder();
    if (lap === finalThirdStart) finalThirdOrder = [...order];
    if (order.length === 0) continue;
    const newLeader = order[0];
    lapsLed.set(newLeader, (lapsLed.get(newLeader) ?? 0) + 1);
    if (leader !== null && newLeader !== leader && !retired.has(leader)) {
      push(lap, "info", `${bySlug.get(newLeader)?.name} sweeps past ${bySlug.get(leader)?.name} for the lead on lap ${lap}.`);
    } else if (lap % quarter === 0 && lap < laps) {
      push(lap, "info", `Lap ${lap}/${laps} — ${bySlug.get(newLeader)?.name} leads, ${bySlug.get(order[1])?.name ?? "nobody"} chasing.`);
    }
    leader = newLeader;

    if (lap >= finalThirdStart && lap < laps) {
      const leadChar = bySlug.get(newLeader)!;
      const pCrash =
        (SHOWBOAT_CRASH_COEFF * Math.pow(leadChar.traits.showboat / 100, 2) * (0.4 + venue.chaos)) /
        Math.max(finalThirdLaps, 1);
      if (leadChar.traits.showboat > 60 && lap > finalThirdStart + 2 && lap < laps - 3 && rng() < pCrash * 0.35) {
        push(lap, "drama", `${leadChar.name} throws a showboat wobble for the grandstand... and barely holds it.`);
      }
      if (rng() < pCrash) {
        retired.add(newLeader);
        dnfLap.set(newLeader, lap);
        dnfReason.set(newLeader, "crashed while showboating in the lead");
        push(lap, "drama", `${leadChar.name} plays to the crowd one corner too long and slides off while LEADING on lap ${lap}!`);
        leader = null;
      }
    }

    if (lap === lateStart) {
      push(lap, "heart", `Final stretch — this is where the valley's believers find something extra.`);
    }
  }

  // Classification: finishers by time, DNFs by distance covered.
  const finishers = characters.filter((c) => !retired.has(c.slug)).map((c) => c.slug);
  finishers.sort((a, b) => (total.get(a) ?? 0) - (total.get(b) ?? 0));
  const retirees = [...retired].sort(
    (a, b) => (dnfLap.get(b) ?? 0) - (dnfLap.get(a) ?? 0) || (total.get(a) ?? 0) - (total.get(b) ?? 0)
  );
  const classified = [...finishers, ...retirees];
  const winnerTime = finishers.length ? total.get(finishers[0])! : 0;

  const results: SimResult[] = classified.map((slug, i) => {
    const c = bySlug.get(slug)!;
    const isDnf = retired.has(slug);
    return {
      position: i + 1,
      slug,
      name: c.name,
      number: c.number,
      color: c.color,
      dnf: isDnf,
      dnfReason: isDnf ? (dnfReason.get(slug) ?? null) : null,
      gapSeconds: isDnf ? null : Math.round((total.get(slug)! - winnerTime) * 100) / 100,
      lapsLed: lapsLed.get(slug) ?? 0,
    };
  });

  // Late-surge shoutouts.
  for (const slug of finishers) {
    const before = finalThirdOrder.indexOf(slug);
    const after = classified.indexOf(slug);
    const c = bySlug.get(slug)!;
    if (before >= 0 && before - after >= 3 && c.traits.heart >= 70) {
      push(laps, "heart", `${c.name} comes alive in the closing laps — up ${before - after} spots when it matters.`);
    }
  }

  const winner = results[0];
  push(laps, "finish", `Checkered flag! ${winner.name} wins at ${venue.name}${results[1]?.gapSeconds != null ? ` by ${results[1].gapSeconds.toFixed(1)}s` : ""}.`);

  return { events, results };
}

// ── Monte Carlo — the "Run 100 races" button ──────────────────────────
export interface WinProb {
  slug: string;
  name: string;
  color: string;
  wins: number;
  podiums: number;
  pct: number;
}

export function winProbabilities(
  characters: CharacterCard[],
  venue: VenueCard,
  n: number,
  seed: number
): WinProb[] {
  const wins = new Map<string, number>();
  const podiums = new Map<string, number>();
  for (let i = 0; i < n; i++) {
    const { results } = simulateRace(characters, venue, seed + i * 7919, false);
    wins.set(results[0].slug, (wins.get(results[0].slug) ?? 0) + 1);
    for (const r of results.slice(0, 3)) {
      podiums.set(r.slug, (podiums.get(r.slug) ?? 0) + 1);
    }
  }
  return characters
    .map((c) => ({
      slug: c.slug,
      name: c.name,
      color: c.color,
      wins: wins.get(c.slug) ?? 0,
      podiums: podiums.get(c.slug) ?? 0,
      pct: Math.round(((wins.get(c.slug) ?? 0) / n) * 100),
    }))
    .sort((a, b) => b.wins - a.wins || b.podiums - a.podiums || a.name.localeCompare(b.name));
}
