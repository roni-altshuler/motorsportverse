/**
 * Site-specific tests for RaceIQ F2's published-data contract.
 *
 * These run against the COMMITTED JSON rather than a fixture, on purpose. The
 * shared suite under `__tests__/shared/` tests components; this tests that the
 * data those components are handed is the shape the TypeScript types promise —
 * which is exactly the seam that breaks when a Python export changes and the
 * TS types are updated in a later commit.
 *
 * The Python side has the same guard in `tests/test_website_data_schema.py`.
 * Both exist because they fail at different times: the pydantic mirror fails in
 * the pipeline, this fails in the site build.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const DATA = join(process.cwd(), "public", "data");

function readJson<T>(...segments: string[]): T {
  return JSON.parse(readFileSync(join(DATA, ...segments), "utf8")) as T;
}

describe("f2.json", () => {
  const data = readJson<Record<string, unknown>>("f2.json");

  it("names the season it describes", () => {
    expect(typeof data.season).toBe("number");
    expect(data.sport).toBeTruthy();
  });

  it("publishes a calendar with a round number on every entry", () => {
    const calendar = data.calendar as Array<Record<string, unknown>>;
    expect(Array.isArray(calendar)).toBe(true);
    expect(calendar.length).toBeGreaterThan(0);
    for (const round of calendar) {
      expect(typeof round.round).toBe("number");
      expect(round.name).toBeTruthy();
    }
  });

  it("numbers the calendar contiguously from 1", () => {
    const rounds = (data.calendar as Array<{ round: number }>).map((r) => r.round);
    expect(rounds).toEqual(Array.from({ length: rounds.length }, (_, i) => i + 1));
  });

  it("gives every driver in the standings a code and a position", () => {
    const standings = data.driverStandings as Array<Record<string, unknown>>;
    expect(standings.length).toBeGreaterThan(0);
    for (const entry of standings) {
      expect(typeof entry.code).toBe("string");
      expect((entry.code as string).length).toBeGreaterThan(0);
      expect(typeof entry.position).toBe("number");
    }
  });

  it("has no duplicate driver codes — a repeat double-counts points", () => {
    const codes = (data.driverStandings as Array<{ code: string }>).map((d) => d.code);
    expect(new Set(codes).size).toBe(codes.length);
  });
});

describe("probabilities", () => {
  const round = readJson<Record<string, Record<string, Record<string, Record<string, { probability: number }>>>>>(
    "probabilities",
    "round_01.json",
  );

  const raceTypes = ["sprint", "feature"] as const;
  const MASS: Record<string, number> = { win: 1, podium: 3, top6: 6, top10: 10 };

  it.each(raceTypes)("%s publishes every market", (raceType) => {
    expect(Object.keys(round[raceType].markets).sort()).toEqual(
      ["podium", "top10", "top6", "win"],
    );
  });

  it.each(raceTypes)(
    "%s probabilities are all inside [0,1]",
    (raceType) => {
      for (const entries of Object.values(round[raceType].markets)) {
        for (const entry of Object.values(entries)) {
          expect(entry.probability).toBeGreaterThanOrEqual(0);
          expect(entry.probability).toBeLessThanOrEqual(1);
        }
      }
    },
  );

  it.each(raceTypes)(
    "%s markets sum to the size of the set they describe",
    (raceType) => {
      // The regression test for the 2026-08 defect: per-competitor isotonic
      // calibration does not preserve the simplex, and these numbers are
      // rendered straight as percentages. A win column that adds to 160% is a
      // lie about the field on screen. See docs/KNOWN_ISSUES.md.
      for (const [market, entries] of Object.entries(round[raceType].markets)) {
        const total = Object.values(entries).reduce((sum, e) => sum + e.probability, 0);
        expect(total).toBeCloseTo(MASS[market], 1);
      }
    },
  );
});

describe("evidence.json", () => {
  const evidence = readJson<Record<string, unknown>>("evidence.json");

  it("states whether a benchmark is available at all", () => {
    expect(typeof evidence.available).toBe("boolean");
  });

  it("labels its basis, so a forward record is never read as a backtest", () => {
    expect(String(evidence.basis)).toMatch(/forward evaluation/i);
  });

  it("always carries at least the cross-series caveat, win or lose", () => {
    const caveats = evidence.caveats as string[];
    expect(caveats.length).toBeGreaterThan(0);
    expect(caveats.join(" ")).toMatch(/only comparable within this series/i);
  });

  it("pairs every comparison on rounds both sides scored", () => {
    const comparisons = evidence.comparisons as Array<{ nRounds: number; rounds: number[] }>;
    for (const comparison of comparisons) {
      expect(comparison.rounds.length).toBe(comparison.nRounds);
    }
  });

  it("never claims a verdict below the minimum round count", () => {
    const comparisons = evidence.comparisons as Array<{ nRounds: number; verdict: string }>;
    for (const comparison of comparisons) {
      if (comparison.nRounds < 5) {
        expect(comparison.verdict).toBe("insufficient");
      }
    }
  });
});

describe("calibration_summary.json", () => {
  const summary = readJson<Record<string, unknown>>("calibration_summary.json");

  it("does not claim calibration on synthetic data", () => {
    if (summary.applied === true) {
      expect(String(summary.dataLimitation ?? "")).not.toMatch(/synthetic/i);
      expect(Number(summary.trainingRounds)).toBeGreaterThanOrEqual(3);
    }
  });
});
