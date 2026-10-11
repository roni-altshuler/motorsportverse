import { render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import type { GridBaselineArtifact, GridBaselineReceipt, RoundData, SeasonData } from "@/types";
import { getGridBaseline } from "@/lib/gridBaseline";
import PublicationHoldPage from "@/components/race-detail/PublicationHoldPage";

const read = (path: string) => JSON.parse(readFileSync(`public/data/${path}`, "utf8"));
const season: SeasonData = read("season.json");
const round: RoundData = read("rounds/round_17.json");
const race = season.calendar.find((r) => r.round === 17)!;
const artifact: GridBaselineArtifact = read("baselines/2026_round_17_f994d9796f18.json");
const receipt: GridBaselineReceipt = read("baselines/2026_round_17.json");

it("shows a named grid-baseline pick alongside the intact publication hold and separate qualifying/grid", () => {
  render(<PublicationHoldPage data={round} race={race} />);
  const baseline = screen.getByRole("region", { name: "Official-grid baseline" });
  expect(within(baseline).getByRole("heading", { name: "Max Verstappen" })).toBeInTheDocument();
  expect(within(baseline).getByText(/No win probability is assigned/)).toBeInTheDocument();
  expect(
    within(baseline).getByText(/own record and is excluded from model accuracy/),
  ).toBeInTheDocument();
  expect(within(baseline).getByText(/06:53:07 UTC/)).toBeInTheDocument();
  expect(within(baseline).getByText(/07:09:02 UTC/)).toBeInTheDocument();
  expect(screen.getByText("Forecast withheld")).toBeInTheDocument();
  expect(screen.getByText("Withdrawn · excluded from accuracy")).toBeInTheDocument();
  expect(
    within(screen.getByRole("table", { name: "Qualifying" }))
      .getByText("George Russell")
      .closest("tr"),
  ).toHaveTextContent(/^6/);
  expect(
    within(screen.getByRole("table", { name: "Starting grid · after penalties" }))
      .getByText("George Russell")
      .closest("tr"),
  ).toHaveTextContent(/^21/);
});

it.each(["round", "date", "circuit"] as const)(
  "does not display another event's baseline when %s changes",
  (field) => {
    const changed = { ...race, [field]: field === "round" ? 16 : "different" };
    expect(getGridBaseline(round, changed)).toBeNull();
  },
);

it.each(["backdate", "probability", "wrong-grid", "late-receipt", "wrong-stream"])(
  "fails closed for %s",
  (condition) => {
    const a: GridBaselineArtifact = JSON.parse(JSON.stringify(artifact)),
      r: GridBaselineReceipt = JSON.parse(JSON.stringify(receipt)),
      d: RoundData = JSON.parse(JSON.stringify(round));
    if (condition === "backdate") a.generatedAt = "2026-10-10T06:00:00Z";
    if (condition === "probability")
      (a as unknown as { probabilities: object }).probabilities = { VER: 0.99 };
    if (condition === "wrong-grid")
      d.weekendResults!.sessions.find((s) => s.key === "startingGrid")!.rows[0].position = 2;
    if (condition === "late-receipt") r.stagedAt = "2026-10-11T12:00:00Z";
    if (condition === "wrong-stream")
      r.evaluationStream = "models" as GridBaselineReceipt["evaluationStream"];
    expect(getGridBaseline(d, race, a, r)).toBeNull();
  },
);

it("preserves the independently sealed baseline after the race without resealing it", () => {
  expect(getGridBaseline(round, race)?.artifact.generatedAt).toBe("2026-10-11T06:53:07.672909Z");
});
