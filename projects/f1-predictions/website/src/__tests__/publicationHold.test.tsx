import { render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import PublicationHoldPage from "@/components/race-detail/PublicationHoldPage";
import { getRaceArt } from "@/lib/raceArt";
import type { RoundData, SeasonData } from "@/types";

const season: SeasonData = JSON.parse(readFileSync(resolve("public/data/season.json"), "utf8"));
function load(round: number): RoundData {
  return JSON.parse(readFileSync(resolve(`public/data/rounds/round_${round}.json`), "utf8"));
}

describe("reviewed event publication", () => {
  it("does not present Sakhir imagery as the relocated Sepang event", () => {
    expect(getRaceArt("Bahrain", 16, "/motorsportverse/projects/f1", "sepang")).toEqual({
      src: null,
      credit: "Sepang venue imagery not verified",
    });
    expect(getRaceArt("Bahrain", 4, "", "bahrain").src).toContain("Bahrain_International_Circuit");
  });
  it("withholds Singapore's forecast while keeping qualifying and the penalty-adjusted grid distinct", () => {
    render(
      <PublicationHoldPage data={load(17)} race={season.calendar.find((r) => r.round === 17)!} />,
    );
    expect(screen.getByText("Forecast withheld")).toBeInTheDocument();
    expect(screen.getByText("Withdrawn · excluded from accuracy")).toBeInTheDocument();
    expect(screen.getByText(/No verified race result/)).toBeInTheDocument();
    expect(screen.getByText(/20:00 Singapore/)).toHaveTextContent("12:00:00 UTC");
    const qualifying = screen.getByRole("table", { name: "Qualifying" });
    const grid = screen.getByRole("table", { name: "Starting grid · after penalties" });
    expect(within(qualifying).getByText("George Russell").closest("tr")).toHaveTextContent(/^6/);
    expect(within(grid).getByText("George Russell").closest("tr")).toHaveTextContent(/^21/);
    expect(screen.queryByText(/72%/)).not.toBeInTheDocument();
    expect(screen.getByText(/Original forecast preserved/)).toHaveTextContent("10:22:59 UTC");
  });

  it("publishes the verified Sepang result without inventing a pre-race forecast or grade", () => {
    render(
      <PublicationHoldPage data={load(16)} race={season.calendar.find((r) => r.round === 16)!} />,
    );
    expect(screen.getByText("Result without a forecast")).toBeInTheDocument();
    expect(screen.getByText("Unavailable · no pre-race forecast")).toBeInTheDocument();
    expect(screen.getByText("Verified classification available")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Race result" })).toBeInTheDocument();
    expect(screen.queryByText(/Predicted podium/)).not.toBeInTheDocument();
  });
});
