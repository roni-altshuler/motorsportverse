import { createHash, webcrypto } from "node:crypto";
import { TextEncoder } from "node:util";
import { findExplorerReview, loadSchematic, validateSchematic } from "@/lib/circuitExplorer";
import { body, pngBytes, review, schematic } from "@/test-support/circuitExplorer";

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

describe("intent-loaded manifest and image integrity", () => {
  const originalCrypto = Object.getOwnPropertyDescriptor(globalThis, "crypto");
  const originalEncoder = Object.getOwnPropertyDescriptor(globalThis, "TextEncoder");
  const originalFetch = globalThis.fetch;
  const originalDecode = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, "decode");
  const originalWidth = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, "naturalWidth");
  const originalHeight = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, "naturalHeight");
  const originalCreate = Object.getOwnPropertyDescriptor(URL, "createObjectURL");
  const originalRevoke = Object.getOwnPropertyDescriptor(URL, "revokeObjectURL");
  const decode = jest.fn();
  const createUrl = jest.fn();
  const revokeUrl = jest.fn();
  let width = 12, height = 9;
  beforeAll(() => {
    Object.defineProperty(globalThis, "crypto", { value: webcrypto, configurable: true });
    Object.defineProperty(globalThis, "TextEncoder", { value: TextEncoder, configurable: true });
    Object.defineProperty(HTMLImageElement.prototype, "decode", { value: decode, configurable: true });
    Object.defineProperty(HTMLImageElement.prototype, "naturalWidth", { get: () => width, configurable: true });
    Object.defineProperty(HTMLImageElement.prototype, "naturalHeight", { get: () => height, configurable: true });
    Object.defineProperty(URL, "createObjectURL", { value: createUrl, configurable: true });
    Object.defineProperty(URL, "revokeObjectURL", { value: revokeUrl, configurable: true });
  });
  beforeEach(() => {
    width = 12; height = 9;
    decode.mockReset().mockResolvedValue(undefined);
    createUrl.mockReset().mockReturnValue("blob:qa-verified"); revokeUrl.mockReset();
  });
  afterAll(() => {
    if (originalCrypto) Object.defineProperty(globalThis, "crypto", originalCrypto);
    if (originalEncoder) Object.defineProperty(globalThis, "TextEncoder", originalEncoder);
    globalThis.fetch = originalFetch;
    for (const [owner, key, descriptor] of [
      [HTMLImageElement.prototype, "decode", originalDecode], [HTMLImageElement.prototype, "naturalWidth", originalWidth],
      [HTMLImageElement.prototype, "naturalHeight", originalHeight], [URL, "createObjectURL", originalCreate], [URL, "revokeObjectURL", originalRevoke],
    ] as const) {
      if (descriptor) Object.defineProperty(owner, key, descriptor);
      else delete (owner as unknown as Record<string, unknown>)[key];
    }
  });
  function responses(bytes = pngBytes, manifest = schematic) {
    const text = JSON.stringify(manifest);
    globalThis.fetch = jest.fn()
      .mockResolvedValueOnce({ ok: true, text: async () => text })
      .mockResolvedValueOnce({ ok: true, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) });
    return { ...review, assetSha256: manifest.asset.sha256, manifestSha256: createHash("sha256").update(text).digest("hex") };
  }
  test("fetches, hashes and decodes the exact local image before returning verified bytes", async () => {
    responses();
    const result = await loadSchematic(review, "/f1");
    expect(result.schematic).toEqual(schematic); expect(result.imageUrl).toBe("blob:qa-verified");
    expect(fetch).toHaveBeenNthCalledWith(1, "/f1/circuit-explorer/qa/manifest.json", { signal: undefined });
    expect(fetch).toHaveBeenNthCalledWith(2, "/f1/circuit-explorer/qa/map.png", { signal: undefined });
    expect(decode).toHaveBeenCalledTimes(1);
    expect(revokeUrl).not.toHaveBeenCalled(); result.release(); result.release();
    expect(revokeUrl).toHaveBeenCalledTimes(1); expect(revokeUrl).toHaveBeenCalledWith("blob:qa-verified");
  });
  test("changed bytes do not acquire a reviewed status", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({ ok: true, text: async () => `${body} ` });
    await expect(loadSchematic(review)).rejects.toThrow("manifest changed");
  });
  test("missing manifest never substitutes a made-up circuit", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({ ok: false });
    await expect(loadSchematic(review)).rejects.toThrow("unavailable");
  });
  test("a missing image never creates a display URL", async () => {
    responses(); (fetch as jest.Mock).mockReset().mockResolvedValueOnce({ ok: true, text: async () => body }).mockResolvedValueOnce({ ok: false, status: 404 });
    await expect(loadSchematic(review)).rejects.toThrow("image unavailable");
    expect(createUrl).not.toHaveBeenCalled(); expect(decode).not.toHaveBeenCalled();
  });
  test("different bytes at the same path fail their actual hash", async () => {
    const changed = Buffer.from(pngBytes); changed[changed.length - 1] ^= 1; responses(changed);
    await expect(loadSchematic(review)).rejects.toThrow("image bytes changed"); expect(createUrl).not.toHaveBeenCalled();
  });
  test("a byte-count mismatch fails before image decoding", async () => {
    responses(pngBytes.subarray(0, -1));
    await expect(loadSchematic(review)).rejects.toThrow("image bytes changed"); expect(decode).not.toHaveBeenCalled();
  });
  test("valid bytes with different decoded dimensions are rejected and released", async () => {
    responses(); width = 13;
    await expect(loadSchematic(review)).rejects.toThrow("dimensions changed"); expect(revokeUrl).toHaveBeenCalledTimes(1);
  });
  test("a corrupt PNG with a matching declared hash still has to decode", async () => {
    const bytes = pngBytes.subarray(0, 16);
    const manifest = { ...schematic, asset: { ...schematic.asset, bytes: bytes.length, sha256: createHash("sha256").update(bytes).digest("hex") } };
    const expected = responses(bytes, manifest); decode.mockRejectedValueOnce(new Error("Cannot decode PNG"));
    await expect(loadSchematic(expected)).rejects.toThrow("Cannot decode PNG"); expect(revokeUrl).toHaveBeenCalledTimes(1);
  });
  test("a non-PNG payload cannot masquerade as a PNG even with matching hashes", async () => {
    const bytes = Buffer.from("not PNG");
    const manifest = { ...schematic, asset: { ...schematic.asset, bytes: bytes.length, sha256: createHash("sha256").update(bytes).digest("hex") } };
    const expected = responses(bytes, manifest);
    await expect(loadSchematic(expected)).rejects.toThrow("not PNG"); expect(createUrl).not.toHaveBeenCalled();
  });
  test("decoding remains pending until the decoder resolves", async () => {
    responses(); let finish!: () => void;
    decode.mockImplementationOnce(() => new Promise<void>(resolve => { finish = resolve; }));
    let resolved = false; const pending = loadSchematic(review).then(value => { resolved = true; return value; });
    while (!decode.mock.calls.length) await new Promise(resolve => setTimeout(resolve, 0));
    expect(resolved).toBe(false); finish(); const loaded = await pending; loaded.release();
  });
  test("cancelling a pending decode immediately releases the URL", async () => {
    responses(); decode.mockImplementationOnce(() => new Promise<void>(() => {}));
    const controller = new AbortController(); const pending = loadSchematic(review, "", controller.signal);
    const rejected = expect(pending).rejects.toMatchObject({ name: "AbortError" });
    while (!decode.mock.calls.length) await new Promise(resolve => setTimeout(resolve, 0));
    controller.abort(); await rejected; expect(revokeUrl).toHaveBeenCalledTimes(1);
  });
});
