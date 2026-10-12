import { render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import PublicationHoldPage from "@/components/race-detail/PublicationHoldPage";
import { getRaceArt } from "@/lib/raceArt";
import type { RaceCalendarEntry, RoundData } from "@/types";

const fixtures = resolve(__dirname, "fixtures/publication-hold");
const calendar: Record<string, RaceCalendarEntry> = JSON.parse(
  readFileSync(resolve(fixtures, "calendar.json"), "utf8"),
);
function load(name: string): RoundData {
  return JSON.parse(readFileSync(resolve(fixtures, name), "utf8"));
}

describe("reviewed event publication", () => {
  it("does not present Sakhir imagery as the relocated Sepang event", () => {
    expect(getRaceArt("Bahrain", 16, "/motorsportverse/projects/f1", "sepang")).toEqual({
      src: null,
      credit: "Sepang venue imagery not verified",
    });
    expect(getRaceArt("Bahrain", 4, "", "bahrain").src).toContain("Bahrain_International_Circuit");
  });
  it.each([
    ["before a result", "singapore-no-result.json", false],
    ["after a result", "singapore-result-available.json", true],
  ] as const)(
    "withholds Singapore's forecast %s while keeping qualifying and the penalty-adjusted grid distinct",
    (_state, fixture, hasResult) => {
      render(<PublicationHoldPage data={load(fixture)} race={calendar["17"]} />);
      expect(screen.getByText("Forecast withheld")).toBeInTheDocument();
      expect(screen.getByText("Withdrawn · excluded from accuracy")).toBeInTheDocument();
      if (hasResult) {
        expect(screen.getByText("Verified classification available")).toBeInTheDocument();
        expect(screen.queryByText("No verified race result")).not.toBeInTheDocument();
        expect(screen.getByRole("table", { name: "Grand Prix Result" })).toBeInTheDocument();
      } else {
        expect(screen.getByText("No verified race result")).toBeInTheDocument();
        expect(screen.queryByText("Verified classification available")).not.toBeInTheDocument();
        expect(
          screen.queryByRole("table", { name: /^(Grand Prix Result|Race result)$/ }),
        ).not.toBeInTheDocument();
      }
      expect(screen.getByText(/20:00 Singapore/)).toHaveTextContent("12:00:00 UTC");
      const qualifying = screen.getByRole("table", { name: "Qualifying" });
      const grid = screen.getByRole("table", { name: "Starting grid · after penalties" });
      expect(within(qualifying).getByText("George Russell").closest("tr")).toHaveTextContent(/^6/);
      expect(within(grid).getByText("George Russell").closest("tr")).toHaveTextContent(/^21/);
      expect(screen.queryByText(/72%/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Predicted podium/)).not.toBeInTheDocument();
      expect(screen.getByText(/Original forecast preserved/)).toHaveTextContent("10:22:59 UTC");
    },
  );

  it("publishes the verified Sepang result without inventing a pre-race forecast or grade", () => {
    render(
      <PublicationHoldPage
        data={load("sepang-result-without-forecast.json")}
        race={calendar["16"]}
      />,
    );
    expect(screen.getByText("Result without a forecast")).toBeInTheDocument();
    expect(screen.getByText("Unavailable · no pre-race forecast")).toBeInTheDocument();
    expect(screen.getByText("Verified classification available")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Race result" })).toBeInTheDocument();
    expect(screen.queryByText(/Predicted podium/)).not.toBeInTheDocument();
  });
});
