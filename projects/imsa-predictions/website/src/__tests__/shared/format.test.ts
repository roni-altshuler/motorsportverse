/**
 * The absent-renders-as-absent contract.
 *
 * DESIGN.md §8.1: `—`, never `0`. "No prediction published" and "predicted
 * last" are different facts, and a UI that draws them identically is lying
 * about one of them. These tests are the enforcement.
 *
 * Synced to every series site — edit the canonical copy under
 * projects/f1-predictions/website/src/__tests__/shared/.
 */
import {
  ABSENT,
  count,
  num,
  ordinal,
  pct,
  points,
  raceDate,
  signed,
  stamp,
} from "@/components/ui/format";

describe("absent renders as absent", () => {
  const formatters: Array<[string, (v: never) => string]> = [
    ["pct", pct as never],
    ["num", num as never],
    ["signed", signed as never],
    ["count", count as never],
    ["points", points as never],
    ["ordinal", ordinal as never],
  ];

  it.each(formatters)("%s(null) is the em dash, never a zero", (_name, fn) => {
    expect(fn(null as never)).toBe(ABSENT);
  });

  it.each(formatters)("%s(undefined) is the em dash", (_name, fn) => {
    expect(fn(undefined as never)).toBe(ABSENT);
  });

  it.each(formatters)("%s(NaN) is the em dash", (_name, fn) => {
    expect(fn(NaN as never)).toBe(ABSENT);
  });

  it("never renders a missing value as 0", () => {
    for (const [, fn] of formatters) {
      expect(fn(null as never)).not.toMatch(/0/);
    }
  });
});

describe("pct", () => {
  it("renders a probability as text, because a bar cannot be read", () => {
    expect(pct(0.634)).toBe("63.4%");
  });

  it("keeps a genuine zero distinct from missing", () => {
    expect(pct(0)).toBe("0.0%");
    expect(pct(null)).toBe(ABSENT);
  });

  it("honours the requested precision", () => {
    expect(pct(0.5, 0)).toBe("50%");
  });
});

describe("signed", () => {
  it("always shows the sign — a delta reads wrong without it", () => {
    expect(signed(1.5)).toBe("+1.50");
    expect(signed(-1.5)).toBe("-1.50");
  });

  it("treats zero as non-negative", () => {
    expect(signed(0)).toBe("+0.00");
  });
});

describe("ordinal", () => {
  it("handles the teens, which the naive rule gets wrong", () => {
    expect(ordinal(11)).toBe("11th");
    expect(ordinal(12)).toBe("12th");
    expect(ordinal(13)).toBe("13th");
    expect(ordinal(21)).toBe("21st");
  });

  it("renders positions 1-3 correctly", () => {
    expect(ordinal(1)).toBe("1st");
    expect(ordinal(2)).toBe("2nd");
    expect(ordinal(3)).toBe("3rd");
  });

  it("refuses position 0 — that is missing data that survived a `|| 0`", () => {
    expect(ordinal(0)).toBe(ABSENT);
    expect(ordinal(-1)).toBe(ABSENT);
  });
});

describe("points", () => {
  it("drops the decimal on whole points but keeps a half point", () => {
    expect(points(25)).toBe("25");
    expect(points(0.5)).toBe("0.5");
  });
});

describe("timestamps", () => {
  it("labels a stamp UTC — these sites serve every timezone at once", () => {
    expect(stamp("2026-07-08T06:28:26Z")).toMatch(/UTC$/);
  });

  it("renders an unparseable date as absent rather than 'Invalid Date'", () => {
    expect(stamp("not a date")).toBe(ABSENT);
    expect(raceDate("not a date")).toBe(ABSENT);
  });

  it("renders an empty timestamp as absent", () => {
    expect(stamp(null)).toBe(ABSENT);
    expect(raceDate(undefined)).toBe(ABSENT);
  });
});
