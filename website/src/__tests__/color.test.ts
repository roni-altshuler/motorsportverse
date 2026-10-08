import { accentInk } from "@/lib/color";

describe("solid project launch labels", () => {
  it.each(["#1E9BD7", "#D9A441", "#FFD659", "#00BFA6"])(
    "uses dark ink on the light brand accent %s",
    (accent) => expect(accentInk(accent)).toBe("#060910"),
  );
  it.each(["#E10600", "#1E1AF0", "#D31217", "#CC0000", "#004994", "#1E2D49"])(
    "keeps white ink on the deep brand accent %s",
    (accent) => expect(accentInk(accent)).toBe("#ffffff"),
  );
  it("accepts shorthand and retains the existing fallback for non-hex accents", () => {
    expect(accentInk("#fff")).toBe("#060910");
    expect(accentInk("#000")).toBe("#ffffff");
    expect(accentInk("var(--accent)")).toBe("var(--accent-ink)");
    expect(accentInk("#invalid")).toBe("var(--accent-ink)");
  });
});
