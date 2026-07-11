// Client-side Race Night simulator — a TypeScript port of
// src/prism_cup/simulate.py (simplified where the UI doesn't need parity).
// Pure functions over a seeded PRNG: no fs, no fetch, safe for "use client".

import {
  ITEM_TIER_WEIGHTS,
  ITEMS_BY_ID,
  RACERS,
  RACERS_BY_ID,
  TRACKS_BY_ID,
  type SimTrack,
} from "@/lib/simConfig";

export type FrameKind =
  | "grid"
  | "lap"
  | "boost"
  | "seeker"
  | "block"
  | "spin"
  | "comet"
  | "shield"
  | "tempest"
  | "swap"
  | "hook"
  | "fizzle"
  | "finish";

export interface SimFrame {
  kind: FrameKind;
  lap: number;
  text: string;
  racerId?: string;
  targetId?: string;
  itemId?: string;
  /** Running order (racer ids, P1 first) after this frame's action. */
  order: string[];
}

export interface RaceSimResult {
  trackId: string;
  seed: number;
  grid: string[];
  frames: SimFrame[];
  finish: string[];
}

export interface BatchRow {
  racerId: string;
  wins: number;
  podiums: number;
}

export interface BatchResult {
  trackId: string;
  races: number;
  rows: BatchRow[];
}

const ITEM_PICK_CHANCE = 0.42;
const SEEKER_BASE_DROP = 3.0;
const SLICK_BASE_DROP = 2.0;

// ── Seeded PRNG (mulberry32) + helpers ───────────────────────────────

export function makeRng(seed: number): () => number {
  let a = seed | 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gauss(rng: () => number, sigma: number): number {
  const u = Math.max(rng(), 1e-9);
  const v = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v) * sigma;
}

function shuffle<T>(rng: () => number, arr: T[]): T[] {
  const out = [...arr];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function weightedPick(rng: () => number, weights: Record<string, number>): string {
  const entries = Object.entries(weights);
  const total = entries.reduce((s, [, w]) => s + w, 0);
  let roll = rng() * total;
  for (const [id, w] of entries) {
    roll -= w;
    if (roll <= 0) return id;
  }
  return entries[entries.length - 1][0];
}

// ── The race ─────────────────────────────────────────────────────────

function positionTier(position: number, fieldSize: number): "front" | "mid" | "back" {
  const third = fieldSize / 3;
  if (position <= third) return "front";
  if (position > 2 * third) return "back";
  return "mid";
}

function knockDrop(rng: () => number, base: number, knockResistance: number): number {
  const scaled = (base + rng() * 1.5) * (1 - knockResistance / 14);
  return Math.max(1, Math.round(scaled));
}

export function simulateRace(trackId: string, seed: number): RaceSimResult {
  const track: SimTrack = TRACKS_BY_ID[trackId];
  const rng = makeRng(seed);
  let order = shuffle(rng, RACERS.map((r) => r.id));
  const grid = [...order];
  const n = order.length;
  const shields = new Set<string>();
  const frames: SimFrame[] = [];

  const name = (rid: string) => RACERS_BY_ID[rid].short;
  const push = (frame: Omit<SimFrame, "order">) => frames.push({ ...frame, order: [...order] });
  const moveBack = (rid: string, places: number): number => {
    const i = order.indexOf(rid);
    const j = Math.min(n - 1, i + places);
    order.splice(j, 0, order.splice(i, 1)[0]);
    return j - i;
  };
  const moveUp = (rid: string, places: number): number => {
    const i = order.indexOf(rid);
    const j = Math.max(0, i - places);
    order.splice(j, 0, order.splice(i, 1)[0]);
    return i - j;
  };

  push({ kind: "grid", lap: 0, text: `Grid set — ${name(order[0])} on pole at ${track.name}` });

  const applyItem = (rid: string, itemId: string, lap: number, pos: number) => {
    const itemName = ITEMS_BY_ID[itemId].name;
    switch (itemId) {
      case "seeker-orb": {
        const leader = order[0];
        if (leader === rid) {
          push({ kind: "fizzle", lap, racerId: rid, itemId,
            text: `${name(rid)}'s Seeker Orb spirals off — nobody ahead to hunt` });
          return;
        }
        if (shields.has(leader)) {
          shields.delete(leader);
          push({ kind: "block", lap, racerId: leader, targetId: rid, itemId,
            text: `${name(leader)}'s Static Shield crackles and eats the Seeker Orb` });
          return;
        }
        const lost = moveBack(leader, knockDrop(rng, SEEKER_BASE_DROP, RACERS_BY_ID[leader].knockResistance));
        push({ kind: "seeker", lap, racerId: rid, targetId: leader, itemId,
          text: `P${pos} ${name(rid)}'s Seeker Orb hunts down leader ${name(leader)} — knocked back ${lost}` });
        return;
      }
      case "slick-patch": {
        const behind = order.slice(order.indexOf(rid) + 1);
        if (behind.length === 0) return;
        const victim = behind[Math.floor(rng() * behind.length)];
        if (shields.has(victim)) {
          shields.delete(victim);
          push({ kind: "block", lap, racerId: victim, targetId: rid, itemId,
            text: `${name(victim)}'s Static Shield fizzes away the Slick Patch` });
          return;
        }
        const lost = moveBack(victim, knockDrop(rng, SLICK_BASE_DROP, RACERS_BY_ID[victim].knockResistance));
        if (lost <= 0) return;
        push({ kind: "spin", lap, racerId: rid, targetId: victim, itemId,
          text: `${name(victim)} spins on ${name(rid)}'s Slick Patch — down ${lost}` });
        return;
      }
      case "comet-boost": {
        const gain = 1 + (rng() < 0.6 ? 1 : 0) + (rng() < 0.25 ? 1 : 0);
        const gained = moveUp(rid, gain);
        push({ kind: "comet", lap, racerId: rid, itemId,
          text: gained > 0
            ? `${name(rid)} rides a Comet Boost up ${gained} place${gained !== 1 ? "s" : ""}`
            : `${name(rid)} lights a Comet Boost and streaks clear at the front` });
        return;
      }
      case "static-shield": {
        shields.add(rid);
        push({ kind: "shield", lap, racerId: rid, itemId, text: `${name(rid)} arms a Static Shield in P${pos}` });
        return;
      }
      case "tempest": {
        const lo = 3;
        const hi = Math.min(9, n - 1);
        if (hi - lo < 2) return;
        const segment = shuffle(rng, order.slice(lo, hi));
        order = [...order.slice(0, lo), ...segment, ...order.slice(hi)];
        push({ kind: "tempest", lap, racerId: rid, itemId,
          text: `${name(rid)}'s Tempest rips through — P${lo + 1}-P${hi} scrambled` });
        return;
      }
      case "swap-beam": {
        const i = order.indexOf(rid);
        if (i === 0) return;
        const ahead = order[i - 1];
        [order[i - 1], order[i]] = [order[i], order[i - 1]];
        push({ kind: "swap", lap, racerId: rid, targetId: ahead, itemId,
          text: `Swap Beam! ${name(rid)} trades places with ${name(ahead)}` });
        return;
      }
      case "magnet-hook": {
        if (moveUp(rid, 1) > 0) {
          push({ kind: "hook", lap, racerId: rid, itemId,
            text: `${name(rid)} reels in a place with the ${itemName}` });
        }
        return;
      }
    }
  };

  for (let lap = 1; lap <= track.laps; lap++) {
    // ── Pace phase: accel-weighted early, top-speed-weighted late. ──
    const early = track.laps > 1 ? 1 - (lap - 1) / (track.laps - 1) : 1;
    const pace: Record<string, number> = {};
    const boosted: [string, number, number][] = [];
    order.forEach((rid, i) => {
      const r = RACERS_BY_ID[rid];
      const stat = r.accel * (0.2 + 0.6 * early) + r.topSpeed * (0.8 - 0.6 * early);
      const inertia = (n - i) * 0.62;
      let boost = 0;
      if (rng() < track.boostPadDensity * 0.45) {
        boost = (1.2 + rng() * 2.2) * (0.6 + r.accel / 20);
        boosted.push([rid, boost, i + 1]);
      }
      pace[rid] = stat * 0.3 + inertia + boost + gauss(rng, 0.9 + 0.5 * track.hazard);
    });
    order.sort((a, b) => pace[b] - pace[a]);
    push({ kind: "lap", lap, text: `Lap ${lap} of ${track.laps} — ${name(order[0])} leads` });
    for (const [rid, amount, posBefore] of boosted) {
      const gained = posBefore - (order.indexOf(rid) + 1);
      if (amount > 2.4 && gained >= 2) {
        push({ kind: "boost", lap, racerId: rid,
          text: `${name(rid)} chains the boost pads — up ${gained} places` });
      }
    }

    // ── Item phase: pickups + effects, front to back. ──
    for (const rid of [...order]) {
      const r = RACERS_BY_ID[rid];
      if (rng() >= ITEM_PICK_CHANCE * r.itemLuck) continue;
      const pos = order.indexOf(rid) + 1;
      const itemId = weightedPick(rng, ITEM_TIER_WEIGHTS[positionTier(pos, n)]);
      applyItem(rid, itemId, lap, pos);
    }
  }

  push({ kind: "finish", lap: track.laps,
    text: `Checkered flag — ${RACERS_BY_ID[order[0]].name} takes ${track.name}!` });

  return { trackId, seed, grid, frames, finish: [...order] };
}

// ── Batch mode: run many races, tally wins + podiums per racer. ──────

export function runBatch(trackId: string, races: number, baseSeed?: number): BatchResult {
  const seedRng = makeRng(baseSeed ?? Math.floor(Math.random() * 2 ** 31));
  const wins: Record<string, number> = {};
  const podiums: Record<string, number> = {};
  for (const r of RACERS) {
    wins[r.id] = 0;
    podiums[r.id] = 0;
  }
  for (let i = 0; i < races; i++) {
    const { finish } = simulateRace(trackId, Math.floor(seedRng() * 2 ** 31));
    wins[finish[0]] += 1;
    for (const rid of finish.slice(0, 3)) podiums[rid] += 1;
  }
  const rows: BatchRow[] = RACERS.map((r) => ({
    racerId: r.id,
    wins: wins[r.id],
    podiums: podiums[r.id],
  })).sort((a, b) => b.wins - a.wins || b.podiums - a.podiums);
  return { trackId, races, rows };
}
