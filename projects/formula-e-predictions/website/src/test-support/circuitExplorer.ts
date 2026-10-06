// Synthetic data for shell/guard QA only; never exported as a reviewed venue.
import { createHash } from "node:crypto";
import type { CircuitSchematic, ExplorerReview } from "@/lib/circuitExplorer";

export const schematic: CircuitSchematic = {
  id: "qa-schematic",
  event: { series: "qa", season: 2026, round: 1, venueKey: "qa-venue", layoutId: "qa-layout", date: "2026-10-06" },
  checkedAt: "2026-10-06", totalCorners: 14,
  asset: { path: "/circuit-explorer/qa/map.png", width: 1000, height: 900, sha256: "a".repeat(64), bytes: 1234 },
  source: { creator: "QA author", title: "QA schematic", page: "https://example.org/source", originalUrl: "https://example.org/source.png", revision: "qa-revision", sha1: "b".repeat(40), sha256: "c".repeat(64), bytes: 12345, width: 10000, height: 9000 },
  license: { id: "CC-BY-SA-4.0", url: "https://creativecommons.org/licenses/by-sa/4.0/" },
  modifications: "Resized; three interactive highlights added.",
  transform: { kind: "resize", algorithm: "lanczos3", crop: null, rotationDegrees: 0, colors: "unchanged", overlay: "three interactive highlights" },
  disclaimer: "Schematic for orientation, not telemetry or survey-accurate geometry.",
  references: [{ url: "https://example.org/reference", purpose: "Configuration reference" }],
  corners: [
    { number: 1, name: "QA first", x: 0.8, y: 0.2, description: "First QA highlight." },
    { number: 3, name: "QA middle", x: 0.2, y: 0.2, description: "Middle QA highlight." },
    { number: 14, name: "QA final", x: 0.5, y: 0.8, description: "Final QA highlight." },
  ],
};
export const body = JSON.stringify(schematic);
export const review: ExplorerReview = { id: schematic.id, event: schematic.event, title: "QA venue", manifestPath: "/circuit-explorer/qa/manifest.json", checkedAt: schematic.checkedAt, assetSha256: schematic.asset.sha256, manifestSha256: createHash("sha256").update(body).digest("hex") };
