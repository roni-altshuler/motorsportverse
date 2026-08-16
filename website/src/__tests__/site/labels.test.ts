/**
 * The tech-stack scrub, which is a product rule with a gate.
 *
 * User-facing pages must not name implementation details — "Plackett-Luce",
 * "isotonic", "Elo", "XGBoost", "Monte Carlo". Describe what the model says,
 * not how. The hub is the highest-risk surface for this because its copy is
 * generated from registry `description` fields, which are written by whoever
 * added the project and routinely full of algorithm names.
 */
import { coreLabel, coreLabelShort, modelLabel, scrubTech, tagLabel } from "@/lib/labels";
import { accentText } from "@/lib/color";

describe("scrubTech", () => {
  it("removes algorithm names from registry copy", () => {
    const scrubbed = scrubTech(
      "Uses isotonic calibration and Elo ratings to forecast a round.",
    );
    expect(scrubbed).not.toMatch(/isotonic/i);
    expect(scrubbed).not.toMatch(/\bElo\b/);
  });

  it("leaves ordinary product copy alone", () => {
    const copy = "Race and championship forecasts, scored against real results.";
    expect(scrubTech(copy)).toBe(copy);
  });

  it("returns an empty string for missing copy, never 'undefined'", () => {
    expect(scrubTech(undefined)).toBe("");
    expect(scrubTech("")).toBe("");
  });

  it("repairs the article on template-generated registry text", () => {
    // "a IndyCar project" is what the scaffolder emits; it reads as a typo on
    // the catalog page, which is the most-viewed surface in the repo.
    expect(scrubTech("a IndyCar project")).toBe("an IndyCar project");
    expect(scrubTech("a IMSA project")).toBe("an IMSA project");
  });
});

describe("label lookups", () => {
  it("fall back to the raw key rather than rendering nothing", () => {
    // A registry entry can name a core capability the hub has no label for.
    // Rendering the key is ugly; rendering an empty cell hides a fact.
    expect(coreLabel("not-a-real-key")).toBe("not-a-real-key");
    expect(coreLabelShort("not-a-real-key")).toBe("not-a-real-key");
    expect(modelLabel("not-a-real-key")).toBe("not-a-real-key");
    expect(tagLabel("not-a-real-key")).toBe("not-a-real-key");
  });

  it("translate the keys the registry actually uses", () => {
    expect(coreLabel("calibration")).not.toBe("calibration");
    expect(coreLabel("eval")).not.toBe("eval");
  });
});

describe("accentText", () => {
  it("mixes a brand accent toward white so dark accents stay readable", () => {
    // IMSA navy and Le Mans green are brand colours, not UI colours, and are
    // unreadable as text on the canvas at full strength.
    expect(accentText("#0A2A5E")).toContain("color-mix");
    expect(accentText("#0A2A5E")).toContain("white");
  });

  it("preserves the accent it was given", () => {
    expect(accentText("#E10600")).toContain("#E10600");
  });
});
