import "@testing-library/jest-dom";
import { act, fireEvent, render, screen } from "@testing-library/react";
import HUDHeader from "@/components/race-detail/HUDHeader";
import ResultCoverage from "@/components/ResultCoverage";
import { resultCoverage, type CoverageRound } from "@/lib/resultCoverage";

jest.mock("@/lib/useReducedMotion", () => ({ useReducedMotion: () => true }));

const calendar: CoverageRound[] = [
  { round: 1, name: "Old gap", featureDate: "2026-10-03", completed: false },
  { round: 2, name: "Imported", raceDate: "2026-10-01", completed: true },
  { round: 3, name: "Future", featureDate: "2026-12-06", completed: false },
];
const asOf = "2026-10-06T00:00:00Z";

beforeEach(() => { jest.useFakeTimers(); jest.setSystemTime(new Date(asOf)); });
afterEach(() => jest.useRealTimers());

test("counts holes independently of latest imported round or export time", () => {
  const coverage = resultCoverage(calendar, asOf);
  expect(coverage.pastDue.map((round) => round.round)).toEqual([1]);
  expect(coverage.latest?.round).toBe(2);
  render(<ResultCoverage calendar={calendar} generatedAt={asOf} asOf={asOf} />);
  expect(screen.getByRole("heading", { name: "Result coverage is behind" })).toBeVisible();
  expect(screen.getByText(/1 scheduled round is past due/)).toHaveTextContent("Source availability has not been verified here");
  fireEvent.click(screen.getByText("View past-due rounds"));
  expect(screen.getByRole("link", { name: "R1 · Old gap" })).toHaveAttribute("href", "/race/1");
  expect(screen.queryByRole("link", { name: /Future/ })).not.toBeInTheDocument();
});

test("allows the full race day plus 48 hours and recomputes while open", () => {
  const before = "2026-10-05T23:59:00Z";
  jest.setSystemTime(new Date(before));
  render(<ResultCoverage calendar={calendar} asOf={before} />);
  expect(screen.queryByText("Result coverage is behind")).not.toBeInTheDocument();
  act(() => jest.advanceTimersByTime(60 * 60 * 1000));
  expect(screen.getByText("Result coverage is behind")).toBeVisible();
});

test("a static export is re-evaluated against the visitor's time after hydration", () => {
  render(<ResultCoverage calendar={calendar} asOf="2026-10-01T00:00:00Z" />);
  act(() => jest.advanceTimersByTime(0));
  expect(screen.getByText("Result coverage is behind")).toBeVisible();
});

test("invalid and missing dates stay unknown; all imported does not imply source verification", () => {
  const bad = [{ ...calendar[0], featureDate: "2026-02-30" }, { ...calendar[2], featureDate: undefined }];
  expect(resultCoverage(bad, asOf).unknown).toHaveLength(2);
  const { rerender } = render(<ResultCoverage calendar={bad} asOf={asOf} />);
  expect(screen.getByText("Result coverage needs review")).toBeVisible();
  rerender(<ResultCoverage calendar={[calendar[1]]} asOf={asOf} />);
  expect(screen.getByRole("heading", { name: "Published result coverage" })).toBeVisible();
  expect(screen.getByText(/Source availability has not been verified here/)).toBeVisible();
});


test("a round without imported results is labelled as a snapshot forecast", () => {
  render(<HUDHeader round={7} name="Old round" country={null} completed={false} activeRace="feature" />);
  expect(screen.getByText("Snapshot Forecast")).toBeVisible();
  expect(screen.queryByText("Upcoming Forecast")).not.toBeInTheDocument();
});


test("an absent calendar is an explicit empty state rather than a zero-coverage claim", () => {
  render(<ResultCoverage calendar={[]} asOf={asOf} />);
  expect(screen.getByText("No result coverage published")).toBeVisible();
  expect(screen.getByText(/The season calendar is unavailable/)).toBeVisible();
  expect(screen.getByText("—")).toBeVisible();
  expect(screen.getByText("None yet")).toBeVisible();
});
