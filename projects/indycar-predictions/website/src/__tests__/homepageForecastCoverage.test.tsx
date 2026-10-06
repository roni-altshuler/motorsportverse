import "@testing-library/jest-dom";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import HomePage from "@/components/HomePage";
import { getIndycarData } from "@/lib/indycardata";

jest.mock("@/lib/indycardata", () => ({
  getIndycarData: jest.fn(), getCircuit: () => null, getRound: () => null,
}));
jest.mock("@/components/home/HeroParallax", () => ({
  __esModule: true, default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
jest.mock("@/components/AddToCalendar", () => ({
  __esModule: true, default: ({ race }: { race: { round: number; date?: string; featureDate?: string } }) =>
    <button>Add R{race.round} on {race.date ?? race.featureDate}</button>,
}));
jest.mock("@/components/home/PodiumStage", () => () => null);
jest.mock("@/components/home/RaceCardCarousel", () => () => null);
jest.mock("@/components/home/ChampionshipBento", () => () => null);
jest.mock("@/components/home/ConstructorsConstellation", () => () => null);
jest.mock("@/components/home/LatestResult", () => () => null);
jest.mock("@/components/marketing/TrustBand", () => () => null);
jest.mock("@/components/marketing/HowItWorksDiagram", () => () => null);
jest.mock("@/components/marketing/FeatureOutcomes", () => () => null);
jest.mock("@/components/marketing/TechnicalCredibility", () => () => null);
jest.mock("@/components/marketing/FAQ", () => () => null);
jest.mock("@/components/marketing/FinalCTA", () => () => null);

const asOf = "2026-10-06T12:00:00Z";
const fixture: ReturnType<typeof getIndycarData> = {
  sport: "Explicit QA fixture", season: 2026, generatedAt: asOf,
  completedRounds: 1, lastUpdatedRound: 2, totalRounds: 3,
  calendar: [
    { round: 1, key: "qa-gap", name: "Old coverage gap", country: null, raceDate: "2026-08-01", completed: false, kind: "circuit", trackType: "road", trackGroup: "road_street" },
    { round: 2, key: "qa-imported", name: "Later imported", country: null, raceDate: "2026-09-01", completed: true, kind: "circuit", trackType: "road", trackGroup: "road_street" },
    { round: 3, key: "qa-future", name: "Future forecast", country: "QA future country", raceDate: "2026-12-06", completed: false, kind: "circuit", trackType: "road", trackGroup: "road_street" },
  ],
  driverStandings: [], teamStandings: [], championship: [],
  nextPrediction: { season: 2026, round: 3, venueKey: "qa-future", venueName: "Future forecast", qualifying: [], race: [] },
};

beforeEach(() => {
  jest.useFakeTimers();
  jest.setSystemTime(new Date(asOf));
  jest.mocked(getIndycarData).mockReturnValue(fixture);
});
afterEach(() => jest.useRealTimers());

test("homepage dates the displayed forecast independently of an earlier coverage gap", () => {
  render(<HomePage />);
  act(() => jest.advanceTimersByTime(0));
  const status = screen.getByLabelText("Snapshot forecast status");
  expect(within(status).getByText("Snapshot forecast")).toBeVisible();
  expect(status).toHaveTextContent("R3");
  expect(status).not.toHaveTextContent("Past-due forecast");
  expect(status).toHaveTextContent("in 60d 12h");
  expect(screen.getByRole("heading", { name: "Future forecast" })).toBeVisible();
  expect(screen.getByRole("link", { name: "View snapshot forecast →" })).toHaveAttribute("href", "/race/3");
  expect(screen.getByRole("button", { name: "Add R3 on 2026-12-06" })).toBeVisible();

  const coverage = screen.getByRole("region", { name: "Result coverage" });
  expect(within(coverage).getByText("Result coverage is behind")).toBeVisible();
  expect(coverage).toHaveTextContent("1 scheduled round is past due");
  fireEvent.click(within(coverage).getByText("View past-due rounds"));
  expect(within(coverage).getByRole("link", { name: "R1 · Old coverage gap" })).toBeVisible();
  expect(within(coverage).queryByRole("link", { name: /Future forecast/ })).not.toBeInTheDocument();
});

test("an unmatched forecast never borrows the first unimported calendar round", () => {
  jest.mocked(getIndycarData).mockReturnValue({ ...fixture, calendar: fixture.calendar.slice(0, 2) });
  render(<HomePage />);
  expect(screen.queryByLabelText("Snapshot forecast status")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Add R3/ })).not.toBeInTheDocument();
  expect(screen.getByText("Result coverage is behind")).toBeVisible();
});

