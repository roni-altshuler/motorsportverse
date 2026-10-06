import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  assessCircuitGeometry,
  circuitGeometrySignature,
  type CircuitGeometryReview,
  type CircuitIdentity,
  type CircuitShape,
} from "@/lib/circuitGeometry";
import { CIRCUIT_GEOMETRY_REVIEWS } from "@/lib/circuitGeometryReviews";

// Explicit synthetic contract fixture. This is never a real or published circuit.
const geometry: CircuitShape = {
  viewBox: "0 0 100 100",
  path: "M 10 10 L 90 10 L 90 90 Z",
  corners: [{ number: 1, x: 90, y: 10, name: "QA corner" }],
};
const identity: CircuitIdentity = {
  series: "qa",
  season: 2026,
  venueKey: "qa-venue",
  layoutId: "qa-layout",
};
function review(): CircuitGeometryReview {
  return {
    ...identity,
    layoutId: "qa-layout",
    geometrySignature: circuitGeometrySignature(geometry),
    source: {
      season: 2025,
      event: "QA event",
      session: "R",
      venueKey: "qa-venue",
      layoutId: "qa-layout",
      url: "https://example.com/qa-source",
    },
    referenceUrl: "https://example.com/qa-reference",
    checkedAt: "2026-10-06",
    reuse: {
      basis: "Synthetic QA fixture",
      evidenceUrl: "https://example.com/qa-rights",
      attribution: "QA only",
    },
  };
}

describe("circuit identity and provenance gate", () => {
  it("accepts only a separately reviewed, coordinate-bound fixture", () => {
    expect(assessCircuitGeometry(identity, geometry, [], [review()])).toEqual({
      status: "verified",
      geometry,
    });
  });
  it("treats absent geometry as missing", () => {
    expect(assessCircuitGeometry(identity, null).status).toBe("missing");
  });
  it("does not approve provider labels, timestamps, or self-declared verification", () => {
    const candidate = { ...geometry, source: "fastf1", generatedAt: "2026-10-06", verified: true };
    expect(assessCircuitGeometry(identity, candidate).geometry).toBeNull();
    expect(assessCircuitGeometry(identity, candidate).status).toBe("unverified");
  });
  it.each([
    { series: "other" },
    { season: 2027 },
    { venueKey: "another-venue" },
    { layoutId: "another-layout" },
    { layoutId: null },
  ])("rejects a review for a different requested identity: %j", (change) => {
    expect(
      assessCircuitGeometry({ ...identity, ...change }, geometry, [], [review()]).geometry,
    ).toBeNull();
  });
  it("rejects the same outline under another venue even with an otherwise complete review", () => {
    expect(
      assessCircuitGeometry(
        identity,
        geometry,
        [{ ...identity, venueKey: "other-venue", geometry }],
        [review()],
      ).status,
    ).toBe("identity-conflict");
  });
  it("rejects the same outline under a different layout configuration", () => {
    expect(
      assessCircuitGeometry(
        identity,
        geometry,
        [{ ...identity, layoutId: "oval-configuration", geometry }],
        [review()],
      ).status,
    ).toBe("identity-conflict");
  });
  it("allows repeated rounds at one explicitly reviewed layout", () => {
    expect(
      assessCircuitGeometry(
        identity,
        geometry,
        [
          { ...identity, geometry },
          { ...identity, geometry },
        ],
        [review()],
      ).status,
    ).toBe("verified");
  });
  it("scopes duplicate checks to the requested series and season", () => {
    const catalog = [
      { ...identity, season: 2025, venueKey: "old-key", geometry },
      { ...identity, series: "other-series", venueKey: "another-series-key", geometry },
    ];
    expect(assessCircuitGeometry(identity, geometry, catalog, [review()]).status).toBe("verified");
  });
  it.each(["venueKey", "layoutId"] as const)("rejects a source identity mismatch: %s", (key) => {
    const entry = review();
    entry.source[key] = "different";
    expect(assessCircuitGeometry(identity, geometry, [], [entry]).status).toBe("identity-mismatch");
  });
  it.each(["event", "session", "url"] as const)("requires resolved source evidence: %s", (key) => {
    const entry = review();
    entry.source[key] = "";
    expect(assessCircuitGeometry(identity, geometry, [], [entry]).status).toBe("review-invalid");
  });
  it.each(["basis", "evidenceUrl", "attribution"] as const)(
    "requires recorded reuse evidence: %s",
    (key) => {
      const entry = review();
      entry.reuse[key] = "";
      expect(assessCircuitGeometry(identity, geometry, [], [entry]).status).toBe("review-invalid");
    },
  );
  it("requires a layout reference and review date", () => {
    const entry = review();
    entry.referenceUrl = "";
    expect(assessCircuitGeometry(identity, geometry, [], [entry]).status).toBe("review-invalid");
    entry.referenceUrl = "https://example.com/qa";
    entry.checkedAt = "";
    expect(assessCircuitGeometry(identity, geometry, [], [entry]).status).toBe("review-invalid");
  });
  it.each([
    { ...geometry, path: "M 10 10 L 70 20 Z" },
    { ...geometry, corners: [{ number: 1, x: 89, y: 10 }] },
    { ...geometry, corners: [{ number: 2, x: 90, y: 10 }] },
    { ...geometry, viewBox: "0 0 200 200" },
  ])("invalidates review after geometry or corner changes", (candidate) => {
    expect(assessCircuitGeometry(identity, candidate, [], [review()]).status).toBe(
      "geometry-changed",
    );
  });
  it.each([
    { ...geometry, viewBox: "0 0 NaN 100" },
    { ...geometry, path: "" },
    { ...geometry, corners: [{ number: 0, x: 90, y: 10 }] },
    { ...geometry, corners: [{ number: 1, x: Infinity, y: 10 }] },
    { ...geometry, corners: [geometry.corners[0], geometry.corners[0]] },
  ])("rejects malformed shapes without inventing corners", (candidate) => {
    expect(assessCircuitGeometry(identity, candidate, [], [review()]).status).toBe("invalid");
  });
});

describe("committed geometry regression", () => {
  // All independent site test jobs run in this monorepo. Locate its data root.
  const root = resolve(
    process.cwd(),
    process.cwd().endsWith("projects/f1-predictions/website") ||
      process.cwd().includes("/projects/")
      ? "../../.."
      : "..",
  );
  it.each(["f1", "f2", "f3"])(
    "quarantines the actual Austria/Silverstone conflict in %s without a bulk catalog",
    (series) => {
      const dataRoot = resolve(root, `projects/${series}-predictions/website/public/data`);
      const library =
        series === "f1"
          ? null
          : JSON.parse(readFileSync(resolve(dataRoot, "circuits.json"), "utf8"));
      const keys = series === "f1" ? ["Austria", "Great Britain"] : ["spielberg", "silverstone"];
      for (const [index, venueKey] of keys.entries()) {
        const candidate = library
          ? library[venueKey]
          : JSON.parse(readFileSync(resolve(dataRoot, `rounds/round_0${index + 8}.json`), "utf8"))
              .circuitInfo.geometry;
        expect(
          assessCircuitGeometry(
            { series, season: 2026, venueKey },
            candidate,
            [],
            CIRCUIT_GEOMETRY_REVIEWS,
          ),
        ).toEqual({ status: "identity-conflict", geometry: null });
      }
    },
  );
});
