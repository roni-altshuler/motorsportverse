/**
 * Prism Cup's kart-race simulation.
 *
 * A **fantasy** project: nothing here predicts a real event. What it still owes
 * the reader is determinism — the whole premise is a seeded league regenerated
 * at deploy time, and a simulation that drifted between the server render and
 * the client hydration would show two different results for one race.
 */
import { makeRng, runBatch, simulateRace } from "@/lib/sim";
import { RACERS, TRACKS } from "@/lib/simConfig";

const TRACK_ID = TRACKS[0].id;

describe("makeRng", () => {
  it("is deterministic for a given seed", () => {
    const a = makeRng(2024);
    const b = makeRng(2024);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });

  it("gives different streams for different seeds", () => {
    expect(makeRng(1)()).not.toBe(makeRng(2)());
  });

  it("stays inside [0,1)", () => {
    const rng = makeRng(7);
    for (let i = 0; i < 200; i++) {
      const value = rng();
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThan(1);
    }
  });
});

describe("simulateRace", () => {
  it("is reproducible — the same seed is the same race", () => {
    expect(simulateRace(TRACK_ID, 31).finish).toEqual(
      simulateRace(TRACK_ID, 31).finish,
    );
  });

  it("classifies every racer exactly once", () => {
    const { finish } = simulateRace(TRACK_ID, 12);
    expect(new Set(finish).size).toBe(finish.length);
    expect(finish.length).toBe(RACERS.length);
  });

  it("only classifies racers that exist", () => {
    const ids = new Set(RACERS.map((r) => r.id));
    for (const racerId of simulateRace(TRACK_ID, 4).finish) {
      expect(ids.has(racerId)).toBe(true);
    }
  });

  it("starts every racer on the grid", () => {
    const { grid } = simulateRace(TRACK_ID, 4);
    expect(new Set(grid).size).toBe(RACERS.length);
  });

  it("records the seed and track it was run for", () => {
    const result = simulateRace(TRACK_ID, 77);
    expect(result.seed).toBe(77);
    expect(result.trackId).toBe(TRACK_ID);
  });
});

describe("runBatch", () => {
  it("counts exactly one win per race", () => {
    const batch = runBatch(TRACK_ID, 50, 99);
    expect(batch.rows.reduce((sum, row) => sum + row.wins, 0)).toBe(50);
  });

  it("counts exactly three podiums per race", () => {
    const batch = runBatch(TRACK_ID, 50, 99);
    expect(batch.rows.reduce((sum, row) => sum + row.podiums, 0)).toBe(150);
  });

  it("lists every racer, including those who never won", () => {
    // A leaderboard that silently drops the racers on zero looks like a
    // shorter grid — the fantasy-league version of absent-rendered-as-missing.
    expect(runBatch(TRACK_ID, 20, 5).rows.length).toBe(RACERS.length);
  });

  it("is reproducible for a given base seed", () => {
    expect(runBatch(TRACK_ID, 20, 5).rows).toEqual(runBatch(TRACK_ID, 20, 5).rows);
  });
});
