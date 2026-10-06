import { webcrypto } from "node:crypto";
import { TextEncoder } from "node:util";
import { findExplorerReview, loadSchematic, validateSchematic } from "@/lib/circuitExplorer";
import { body, review, schematic } from "@/test-support/circuitExplorer";

test.each([
  { series: "f2" }, { season: 2025 }, { round: 2 }, { venueKey: "different-venue" },
  { layoutId: "different-layout" }, { date: "2026-10-07" }, { layoutId: "" },
])("does not reuse an unreviewed event/configuration: %p", change => {
  expect(findExplorerReview({ ...review.event, ...change }, [review])).toBeNull();
});

test("exact event context resolves, while absent review remains absent", () => {
  expect(findExplorerReview(review.event, [review])).toBe(review);
  expect(findExplorerReview(review.event, [])).toBeNull();
  expect(validateSchematic(schematic, review)).toBe(schematic);
});

test.each([
  (value: typeof schematic) => { value.source.creator = ""; },
  (value: typeof schematic) => { value.license.url = "https://example.org/unclear-license"; },
  (value: typeof schematic) => { value.modifications = ""; },
  (value: typeof schematic) => { value.source.revision = ""; },
  (value: typeof schematic) => { value.source.sha256 = ""; },
  (value: typeof schematic) => { value.asset.sha256 = "d".repeat(64); },
  (value: typeof schematic) => { value.corners.reverse(); },
  (value: typeof schematic) => { value.corners[1].number = 1; },
  (value: typeof schematic) => { value.corners[0].x = 2; },
  (value: typeof schematic) => { value.event.layoutId = "wrong-layout"; },
])("rejects changed identity, asset, corner order or incomplete credit (%#)", modify => {
  const candidate = JSON.parse(JSON.stringify(schematic));
  modify(candidate);
  expect(validateSchematic(candidate, review)).toBeNull();
});

test.each([null, {}, { ...schematic, source: { creator: 7 } }, { ...schematic, references: [null] }])("malformed manifests fail closed without throwing: %p", value => {
  expect(validateSchematic(value, review)).toBeNull();
});

describe("intent-loaded manifest integrity", () => {
  const originalCrypto = Object.getOwnPropertyDescriptor(globalThis, "crypto");
  const originalEncoder = Object.getOwnPropertyDescriptor(globalThis, "TextEncoder");
  const originalFetch = globalThis.fetch;
  beforeAll(() => {
    Object.defineProperty(globalThis, "crypto", { value: webcrypto, configurable: true });
    Object.defineProperty(globalThis, "TextEncoder", { value: TextEncoder, configurable: true });
  });
  afterAll(() => {
    if (originalCrypto) Object.defineProperty(globalThis, "crypto", originalCrypto);
    if (originalEncoder) Object.defineProperty(globalThis, "TextEncoder", originalEncoder);
    globalThis.fetch = originalFetch;
  });
  test("only fetches its local manifest, honoring the site base path", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({ ok: true, text: async () => body });
    expect(await loadSchematic(review, "/f1")).toEqual(schematic);
    expect(fetch).toHaveBeenCalledWith("/f1/circuit-explorer/qa/manifest.json");
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  test("changed bytes do not acquire a reviewed status", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({ ok: true, text: async () => `${body} ` });
    await expect(loadSchematic(review)).rejects.toThrow("manifest changed");
  });
  test("missing manifest never substitutes a made-up circuit", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({ ok: false });
    await expect(loadSchematic(review)).rejects.toThrow("unavailable");
  });
});
