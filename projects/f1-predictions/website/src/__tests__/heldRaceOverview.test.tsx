import { fireEvent, render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { RaceCalendarEntry, RoundData } from "@/types";
import PublicationHoldPage from "@/components/race-detail/PublicationHoldPage";

const fixtures = resolve(__dirname, "fixtures/publication-hold");
const calendar: Record<string, RaceCalendarEntry> = JSON.parse(
  readFileSync(resolve(fixtures, "calendar.json"), "utf8"),
);
const load = (name: string): RoundData => JSON.parse(readFileSync(resolve(fixtures, name), "utf8"));

it("puts observed leaders and the full race result before the historical baseline and session tables", () => {
  render(
    <PublicationHoldPage data={load("singapore-result-available.json")} race={calendar["17"]} />,
  );
  const leaders = screen.getByRole("list", { name: "Observed race leaders" });
  expect(within(leaders).getByRole("link", { name: "Max Verstappen" })).toHaveAttribute(
    "href",
    "/driver/VER",
  );
  expect(within(leaders).getByRole("link", { name: /Antonelli/ })).toHaveAttribute(
    "href",
    "/driver/ANT",
  );
  expect(within(leaders).queryByText("Lewis Hamilton")).not.toBeInTheDocument();
  expect(screen.getAllByRole("table")[0]).toHaveAttribute("aria-label", "Grand Prix Result");
  expect(screen.getByRole("link", { name: "Full race result →" })).toHaveAttribute(
    "href",
    "#grandPrix",
  );
  expect(screen.getByRole("link", { name: "Explore Circuit →" })).toHaveAttribute(
    "href",
    "/circuits",
  );
  expect(screen.getByText("Withheld")).toBeInTheDocument();
  expect(screen.getByText("Pre-race grid order · no win probabilities")).toBeInTheDocument();
});

it("never treats the pre-race baseline pick as an observed result", () => {
  render(<PublicationHoldPage data={load("singapore-no-result.json")} race={calendar["17"]} />);
  expect(screen.queryByRole("list", { name: "Observed race leaders" })).not.toBeInTheDocument();
  expect(
    screen.getByText("No race classification is recorded in this round yet."),
  ).toBeInTheDocument();
  expect(screen.getByText("Max Verstappen · P1 starter")).toBeInTheDocument();
  expect(screen.getByText("Withheld")).toBeInTheDocument();
});

it("keeps the original baseline and review evidence behind operable, initially closed disclosures", () => {
  render(
    <PublicationHoldPage data={load("singapore-result-available.json")} race={calendar["17"]} />,
  );
  const summary = screen.getByText("Baseline pick and sources");
  expect(summary.closest("details")).not.toHaveAttribute("open");
  fireEvent.click(summary);
  expect(summary.closest("details")).toHaveAttribute("open");
  expect(screen.getByText(/06:53:07 UTC/)).toBeInTheDocument();
  expect(screen.getByText("Forecast hold and event record").closest("details")).not.toHaveAttribute(
    "open",
  );
  fireEvent.click(screen.getByText("Forecast hold and event record"));
  expect(screen.getByText("Withdrawn · excluded from accuracy")).toBeInTheDocument();
  expect(screen.getByText(/Original forecast preserved/)).toHaveTextContent("10:22:59 UTC");
});

it("retains actual results while hiding a baseline whose starting-grid inputs no longer pass the existing guard", () => {
  const data = load("singapore-result-available.json");
  data.weekendResults!.sessions.find(
    (session) => session.key === "startingGrid",
  )!.rows[0].position = 2;
  render(<PublicationHoldPage data={data} race={calendar["17"]} />);
  expect(screen.getByRole("list", { name: "Observed race leaders" })).toBeInTheDocument();
  expect(screen.getByText("Not available for this event")).toBeInTheDocument();
  expect(screen.queryByText("Baseline pick and sources")).not.toBeInTheDocument();
});

it("shows a result without inventing names or timing when session metadata is absent", () => {
  const data = load("singapore-result-available.json");
  data.weekendResults = undefined;
  render(<PublicationHoldPage data={data} race={calendar["17"]} />);
  const leaders = screen.getByRole("list", { name: "Observed race leaders" });
  expect(within(leaders).getByRole("link", { name: "VER" })).toBeInTheDocument();
  expect(within(leaders).queryByText("Max Verstappen")).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Full race result →" })).not.toBeInTheDocument();
});

it("resets disclosures on another event and keeps result-without-forecast status distinct", () => {
  const { rerender } = render(
    <PublicationHoldPage data={load("singapore-result-available.json")} race={calendar["17"]} />,
  );
  fireEvent.click(screen.getByText("Forecast hold and event record"));
  rerender(
    <PublicationHoldPage
      data={load("sepang-result-without-forecast.json")}
      race={calendar["16"]}
    />,
  );
  expect(screen.getByText("Forecast hold and event record").closest("details")).not.toHaveAttribute(
    "open",
  );
  expect(screen.getByText("Unavailable")).toBeInTheDocument();
  expect(screen.getByText("No pre-race model forecast recorded.")).toBeInTheDocument();
  expect(screen.queryByText("Max Verstappen · P1 starter")).not.toBeInTheDocument();
});
