/**
 * The published-data contract, asserted from the SITE side.
 *
 * These run against each site's committed JSON rather than a fixture, on
 * purpose. The shared component tests next door check that components render
 * honestly; this checks that the data those components are handed is the shape
 * they assume — the seam that breaks when a Python export changes and the
 * TypeScript types are updated a commit later.
 *
 * The Python side has the same guard in `tests/test_website_data_schema.py`.
 * Both exist because they fail at different moments: the pydantic mirror fails
 * in the pipeline, this fails in the site build, and only one of those is
 * running when a website-only change lands.
 *
 * Written to DISCOVER rather than hardcode, because the ecosystem publishes
 * several shapes: a single-race series keys markets by race type, the endurance
 * products key by class, and the hub publishes only a registry. A test that
 * named `f3.json` would have to be rewritten for each site and would silently
 * cover nothing on the ones it was not written for.
 *
 * Synced to every site — edit the canonical copy under
 * projects/f1-predictions/website/src/__tests__/shared/.
 */
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const DATA = join(process.cwd(), "public", "data");

// What each market must total across the field: a win market describes one
// slot, a podium three. Mirrors motorsport_core.calibration.MARKET_TARGET_SUM.
const MARKET_TARGET: Record<string, number> = { win: 1, podium: 3, top6: 6, top10: 10 };
const TOLERANCE = 0.02;

type Json = Record<string, unknown>;

const readJson = (...segments: string[]): Json =>
  JSON.parse(readFileSync(join(DATA, ...segments), "utf8")) as Json;

const roundFiles = (dir: string): string[] => {
  const full = join(DATA, dir);
  if (!existsSync(full)) return [];
  return readdirSync(full)
    .filter((f) => /^round_\d+\.json$/.test(f))
    .sort();
};

/**
 * Every {win|podium|top6|top10} block anywhere in the payload, at any depth.
 *
 * Two published shapes, both real: the series sites key a market by competitor
 * (`{ VER: { probability } }`) and the flagship publishes a LIST
 * (`[{ driver, probability }]`). Returning the probabilities rather than the
 * container lets one caller handle both — the Python integrity check had to
 * learn the same lesson, and a version of this that only understood the dict
 * shape silently checked nothing on F1.
 */
function* markets(node: unknown, path = ""): Generator<{ path: string; market: string; values: number[] }> {
  if (Array.isArray(node)) {
    for (const [i, item] of node.entries()) yield* markets(item, `${path}[${i}]`);
    return;
  }
  if (!node || typeof node !== "object") return;
  for (const [key, value] of Object.entries(node as Json)) {
    const probs = key in MARKET_TARGET ? marketValues(value) : null;
    if (probs) yield { path: `${path}.${key}`, market: key, values: probs };
    else yield* markets(value, `${path}.${key}`);
  }
}

/** The probabilities in a market block, whichever shape it takes, else null. */
function marketValues(value: unknown): number[] | null {
  const hasProb = (v: unknown) => v !== null && typeof v === "object" && "probability" in (v as Json);
  const entries = Array.isArray(value)
    ? value
    : value !== null && typeof value === "object"
      ? Object.values(value as Json)
      : [];
  if (entries.length === 0 || !entries.every(hasProb)) return null;
  return entries.map((e) => Number((e as Json).probability));
}

const hasData = existsSync(DATA);

(hasData ? describe : describe.skip)("published data", () => {
  it("publishes at least one JSON document", () => {
    expect(readdirSync(DATA).some((f) => f.endsWith(".json"))).toBe(true);
  });

  it("every JSON file parses", () => {
    const broken: string[] = [];
    const walk = (dir: string) => {
      for (const entry of readdirSync(join(DATA, dir), { withFileTypes: true })) {
        const rel = dir ? `${dir}/${entry.name}` : entry.name;
        if (entry.isDirectory()) walk(rel);
        else if (entry.name.endsWith(".json")) {
          try {
            JSON.parse(readFileSync(join(DATA, rel), "utf8"));
          } catch {
            broken.push(rel);
          }
        }
      }
    };
    walk("");
    expect(broken).toEqual([]);
  });
});

const probabilityRounds = hasData ? roundFiles("probabilities") : [];

(probabilityRounds.length ? describe : describe.skip)("probabilities", () => {
  it("renders no probability outside [0, 1]", () => {
    const bad: string[] = [];
    for (const file of probabilityRounds) {
      for (const { path, values } of markets(readJson("probabilities", file))) {
        for (const [i, p] of values.entries()) {
          if (!Number.isFinite(p) || p < 0 || p > 1) bad.push(`${file}${path}[${i}] = ${String(p)}`);
        }
      }
    }
    expect(bad).toEqual([]);
  });

  it("totals every market to the size of the set it describes", () => {
    // The defect this exists for: per-competitor calibration does not preserve
    // the simplex, so published win markets summed 1.19-1.43 across nine series
    // while every per-file schema test passed. The site renders `probability`
    // straight as a percentage, so an incoherent market is visible to anyone
    // who adds up a column.
    const bad: string[] = [];
    let checked = 0;
    for (const file of probabilityRounds) {
      for (const { path, market, values } of markets(readJson("probabilities", file))) {
        // A market can be larger than the field it describes — a five-car class
        // has no meaningful top ten, and everyone finishes in it.
        const target = Math.min(MARKET_TARGET[market], values.length);
        const total = values.reduce((a, b) => a + b, 0);
        checked += 1;
        if (Math.abs(total - target) > target * TOLERANCE) {
          bad.push(`${file}${path} sums to ${total.toFixed(4)}, expected ${target}`);
        }
      }
    }
    expect(bad).toEqual([]);
    expect(checked).toBeGreaterThan(0);
  });
});

const summaries = hasData
  ? readdirSync(DATA).filter(
      (f) => f.endsWith(".json") && !["evidence.json", "seasons.json", "registry.json"].includes(f),
    )
  : [];

(summaries.length ? describe : describe.skip)("season summary", () => {
  it("numbers any published calendar contiguously from 1", () => {
    const bad: string[] = [];
    for (const file of summaries) {
      const calendar = readJson(file).calendar;
      if (!Array.isArray(calendar) || calendar.length === 0) continue;
      const rounds = calendar.map((r) => (r as Json).round);
      if (!rounds.every((r) => typeof r === "number")) continue;
      const expected = Array.from({ length: rounds.length }, (_, i) => i + 1);
      if (JSON.stringify(rounds) !== JSON.stringify(expected)) {
        bad.push(`${file}: ${JSON.stringify(rounds)}`);
      }
    }
    expect(bad).toEqual([]);
  });

  it("gives every standings entry an identity and a position", () => {
    // Identity is resolved by SHAPE, not by a list of blessed key names. A
    // manufacturer table identifies by `make` and an engine table by `engine`,
    // and a fixed list of code/name/team/driver called both of those anonymous —
    // which is a test failing correct data, the thing that teaches people to
    // ignore tests. Any non-colour string field is an identity.
    const isColour = (v: string) => /^#?[0-9a-f]{3,8}$/i.test(v.trim());
    const PRESENTATION = new Set(["color", "colour", "teamcolor", "teamcolour"]);
    const bad: string[] = [];
    for (const file of summaries) {
      for (const [key, value] of Object.entries(readJson(file))) {
        if (!/standings/i.test(key) || !Array.isArray(value) || value.length === 0) continue;
        for (const [i, entry] of value.entries()) {
          const e = entry as Json;
          const identity = Object.entries(e).some(
            ([k, v]) =>
              typeof v === "string" &&
              v.trim().length > 0 &&
              !PRESENTATION.has(k.toLowerCase()) &&
              !isColour(v),
          );
          if (!identity || typeof e.position !== "number") bad.push(`${file}.${key}[${i}]`);
        }
      }
    }
    expect(bad).toEqual([]);
  });
});

const evidencePath = join(DATA, "evidence.json");
const hasEvidence = existsSync(evidencePath);

(hasEvidence ? describe : describe.skip)("evidence.json", () => {
  // Read guarded, not eagerly: `describe.skip` still EXECUTES its body to
  // collect test names, so an unguarded readFileSync here throws at collection
  // time and fails the whole suite on any site without the file — which is
  // exactly what the ecosystem hub did, since it publishes only a registry.
  const evidence = hasEvidence ? (JSON.parse(readFileSync(evidencePath, "utf8")) as Json) : {};

  it("states whether a benchmark is available at all", () => {
    expect(typeof evidence.available).toBe("boolean");
  });

  it("gives a reason when it is not available, rather than rendering nothing", () => {
    if (evidence.available === false) expect(evidence.reason).toBeTruthy();
  });

  it("carries a verdict and a baseline on every comparison", () => {
    if (evidence.available !== true) return;
    const comparisons = (evidence.comparisons ?? []) as Json[];
    expect(Array.isArray(comparisons)).toBe(true);
    for (const c of comparisons) {
      expect(c.baseline).toBeTruthy();
      expect(["better", "worse", "inconclusive", "insufficient"]).toContain(c.verdict);
    }
  });

  it("never reports a comparison over zero rounds as a result", () => {
    if (evidence.available !== true) return;
    for (const c of ((evidence.comparisons ?? []) as Json[])) {
      if (typeof c.nRounds === "number" && c.nRounds === 0) {
        expect(c.verdict).toBe("insufficient");
      }
    }
  });
});
