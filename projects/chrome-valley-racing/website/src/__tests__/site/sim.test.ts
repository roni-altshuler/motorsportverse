/**
 * Chrome Valley's in-browser race simulation.
 *
 * This is a **fantasy** project: nothing here predicts a real event. What it
 * still owes the reader is that the same seed gives the same race — the whole
 * premise is a deterministic story league regenerated at deploy time, and a
 * simulation that drifted between the server render and the client hydration
 * would show two different results for one race.
 */
import { mulberry32, simulateRace, winProbabilities } from "@/lib/sim";
import { getLeague, getRoster } from "@/lib/data";

const roster = getRoster();
const characters = roster.characters;
const venue = getLeague().venues[0];

describe("mulberry32", () => {
  it("is deterministic for a given seed", () => {
    const a = mulberry32(1234);
    const b = mulberry32(1234);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });

  it("gives different streams for different seeds", () => {
    expect(mulberry32(1)()).not.toBe(mulberry32(2)());
  });

  it("stays inside [0,1)", () => {
    const rng = mulberry32(99);
    for (let i = 0; i < 200; i++) {
      const value = rng();
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThan(1);
    }
  });
});

describe("simulateRace", () => {
  it("is reproducible — the same seed is the same race", () => {
    const first = simulateRace(characters, venue, 7);
    const second = simulateRace(characters, venue, 7);
    expect(first.results.map((r) => r.slug)).toEqual(
      second.results.map((r) => r.slug),
    );
  });

  it("classifies every character exactly once", () => {
    const { results } = simulateRace(characters, venue, 42);
    const slugs = results.map((r) => r.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
    expect(slugs.length).toBe(characters.length);
  });

  it("assigns contiguous finishing positions from 1", () => {
    const { results } = simulateRace(characters, venue, 3);
    const positions = results.map((r) => r.position).sort((a, b) => a - b);
    expect(positions).toEqual(
      Array.from({ length: characters.length }, (_, i) => i + 1),
    );
  });

  it("gives every retirement a reason, never a bare DNF", () => {
    // A DNF with no reason is the fantasy-league version of absent-as-zero:
    // the reader cannot tell "crashed" from "we lost the row".
    for (const seed of [1, 2, 3, 4, 5]) {
      for (const result of simulateRace(characters, venue, seed).results) {
        if (result.dnf) expect(result.dnfReason).toBeTruthy();
      }
    }
  });

  it("produces a commentary feed when asked, and none when not", () => {
    expect(simulateRace(characters, venue, 9, true).events.length).toBeGreaterThan(0);
    expect(simulateRace(characters, venue, 9, false).events.length).toBe(0);
  });
});

describe("winProbabilities", () => {
  it("counts exactly one win per simulated race", () => {
    const probs = winProbabilities(characters, venue, 200, 11);
    expect(probs.reduce((sum, p) => sum + p.wins, 0)).toBe(200);
  });

  it("counts exactly three podiums per simulated race", () => {
    const probs = winProbabilities(characters, venue, 100, 11);
    expect(probs.reduce((sum, p) => sum + p.podiums, 0)).toBe(300);
  });

  it("lists every character, including those who never won", () => {
    expect(winProbabilities(characters, venue, 100, 5).length).toBe(characters.length);
  });

  it("is reproducible for a given seed", () => {
    const a = winProbabilities(characters, venue, 100, 21);
    const b = winProbabilities(characters, venue, 100, 21);
    expect(a.map((p) => p.pct)).toEqual(b.map((p) => p.pct));
  });
});
