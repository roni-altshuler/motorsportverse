import "@testing-library/jest-dom";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render } from "@testing-library/react";
import HeroParallax from "@/components/home/HeroParallax";
import { assessCircuitOutline, assessCircuitGeometry } from "@/lib/circuitGeometry";

jest.mock("@/components/magicui/dot-pattern", () => ({ DotPattern: () => null }));

it("preserves the decorative sweep for the actual Monaco path while explorer review is pending", () => {
  const raw = JSON.parse(readFileSync(resolve("public/data/rounds/round_06.json"), "utf8"));
  const identity = { series: "f1", season: 2026, venueKey: "Monaco" };
  const geometry = assessCircuitOutline(identity, raw.circuitInfo.geometry).geometry;
  const { container } = render(
    <HeroParallax geometry={geometry}>
      <h1>RaceIQ</h1>
    </HeroParallax>,
  );
  expect(container.querySelector(".hero-track-ribbon")).toHaveAttribute("aria-hidden", "true");
  expect(container.querySelector(".ribbon-sweep")).toHaveAttribute(
    "d",
    raw.circuitInfo.geometry.path,
  );
  expect(assessCircuitGeometry(identity, raw.circuitInfo.geometry).geometry).toBeNull();
});
