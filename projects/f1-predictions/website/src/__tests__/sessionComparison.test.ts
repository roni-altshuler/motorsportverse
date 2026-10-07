import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  COMPARISON_SOURCE_HASH,
  formatTimingDelta,
  timingDelta,
  validateSessionComparison,
} from "@/lib/sessionComparison";

const fixture = () =>
  JSON.parse(
    readFileSync(join(process.cwd(), "public/data/session-comparison/2025_Monaco_R.json"), "utf8"),
  );

describe("archived session comparison contract", () => {
  it("accepts the actual committed session and its source fingerprint", () => {
    const data = validateSessionComparison(fixture());
    expect(data.source.sha256).toBe(COMPARISON_SOURCE_HASH);
    expect(data.drivers).toHaveLength(20);
    const a = data.drivers.find((d) => d.code === "NOR")!;
    const b = data.drivers.find((d) => d.code === "RUS")!;
    expect(a.sectorMs).toEqual([19145, 34697, 19379]);
    expect(timingDelta(a.lapMs, b.lapMs)).toBe(184);
    expect(timingDelta(a.sectorMs[1], b.sectorMs[1])).toBe(-7);
  });
  it.each(["season", "id", "date", "kind"])("rejects a mislabeled session %s", (key) => {
    const data = fixture();
    data.session[key] = key === "season" ? 2026 : "unverified";
    expect(() => validateSessionComparison(data)).toThrow();
  });
  it("rejects changed source identity and absent context disclosures", () => {
    const data = fixture();
    data.source.sha256 = "0".repeat(64);
    expect(() => validateSessionComparison(data)).toThrow();
    const undisclosed = fixture();
    undisclosed.source.missingFields = [];
    expect(() => validateSessionComparison(undisclosed)).toThrow();
  });
  it.each([0, -1, Infinity, NaN, 19.145])("rejects invalid timing %s", (value) => {
    const data = fixture();
    data.drivers[0].sectorMs[0] = value;
    expect(() => validateSessionComparison(data)).toThrow();
  });
  it("rejects duplicated drivers, inconsistent sectors and remote portraits", () => {
    for (const mutate of [
      (data: ReturnType<typeof fixture>) => data.drivers.push(data.drivers[0]),
      (data: ReturnType<typeof fixture>) => (data.drivers[0].lapMs += 300),
      (data: ReturnType<typeof fixture>) =>
        (data.drivers[0].portraitPath = "https://example.com/portrait.webp"),
    ]) {
      const data = fixture();
      mutate(data);
      expect(() => validateSessionComparison(data)).toThrow();
    }
  });
  it("allows an empty archive to render an explicit empty state", () => {
    const data = fixture();
    data.drivers = [];
    expect(validateSessionComparison(data).drivers).toEqual([]);
  });
  it("preserves direction when swapping and formats ties without a quicker driver", () => {
    expect(timingDelta(73221, 73405)).toBe(-timingDelta(73405, 73221));
    expect(formatTimingDelta(184)).toBe("+0.184s");
    expect(formatTimingDelta(-7)).toBe("−0.007s");
    expect(formatTimingDelta(0)).toBe("0.000s");
  });
});
