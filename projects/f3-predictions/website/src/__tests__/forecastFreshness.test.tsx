import "@testing-library/jest-dom";
import { act, render, screen, within } from "@testing-library/react";
import ResultCoverage from "@/components/ResultCoverage";
import SnapshotForecastStatus from "@/components/SnapshotForecastStatus";
import HeroCountdown from "@/components/home/HeroCountdown";
import RaceCardCarousel from "@/components/home/RaceCardCarousel";
import { forecastState } from "@/lib/resultCoverage";
import type { CalendarRound } from "@/types/f3";

jest.mock("lucide-react", () => ({ ChevronLeft: () => null, ChevronRight: () => null }));

jest.mock("@/components/magicui/spotlight", () => ({
  Spotlight: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
jest.mock("@/components/magicui/neon-gradient-card", () => ({
  NeonGradientCard: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
jest.mock("@/lib/raceArt", () => ({ getRaceArt: () => null }));

const round: CalendarRound = { round: 1, key: "fixture", name: "Scheduled round", country: null, completed: false, featureDate: "2026-10-03" };
const buildTime = "2026-10-02T00:00:00Z";

beforeEach(() => { jest.useFakeTimers(); jest.setSystemTime(new Date("2026-10-05T00:00:00Z")); });
afterEach(() => jest.useRealTimers());

test("panel, forecast badge and carousel age together after hydration and the grace boundary", () => {
  render(<>
    <ResultCoverage calendar={[round]} asOf={buildTime} />
    <SnapshotForecastStatus round={round} asOf={buildTime} description="R1 · Forecast" />
    <RaceCardCarousel calendar={[round]} nextRound={1} asOf={buildTime} />
  </>);
  const status = screen.getByLabelText("Snapshot forecast status");
  const card = screen.getByRole("link", { name: /Scheduled round/ });
  expect(within(card).getByText(/Next up/)).toBeVisible();
  act(() => jest.advanceTimersByTime(0));
  expect(within(status).getByText("Snapshot forecast")).toBeVisible();
  expect(within(card).getByText(/Snapshot forecast/)).toBeVisible();
  expect(screen.queryByText(/Next up/)).not.toBeInTheDocument();
  expect(screen.queryByText("this weekend")).not.toBeInTheDocument();
  expect(screen.queryByText("Result coverage is behind")).not.toBeInTheDocument();
  act(() => jest.advanceTimersByTime(24 * 60 * 60 * 1000));
  expect(screen.getByText("Result coverage is behind")).toBeVisible();
  expect(within(status).getByText("Past-due forecast")).toBeVisible();
  expect(within(card).getByText(/Past-due forecast/)).toBeVisible();
});

test("a visitor to an old export sees a past-due badge immediately after hydration", () => {
  jest.setSystemTime(new Date("2026-10-06T00:00:00Z"));
  render(<SnapshotForecastStatus round={round} asOf={buildTime} description="R1 · Forecast" />);
  act(() => jest.advanceTimersByTime(0));
  expect(screen.getByText("Past-due forecast")).toBeVisible();
  expect(screen.queryByText(/in \d/)).not.toBeInTheDocument();
});

test("missing or invalid dates stay snapshot forecasts; future and imported states stay distinct", () => {
  const dateKey = "featureDate";
  expect(forecastState(round, buildTime)).toBe("scheduled");
  expect(forecastState(round, "2026-10-03T00:00:00Z")).toBe("snapshot");
  expect(forecastState({ ...round, completed: true }, buildTime)).toBe("completed");
  for (const value of [undefined, "2026-02-30"]) {
    const unknown = { ...round, [dateKey]: value };
    expect(forecastState(unknown, buildTime)).toBe("snapshot");
    const view = render(<RaceCardCarousel calendar={[unknown]} nextRound={1} asOf={buildTime} />);
    expect(screen.getByText(/Snapshot forecast/)).toBeVisible();
    expect(screen.queryByText(/Next up/)).not.toBeInTheDocument();
    view.unmount();
  }
});

test("countdown stops claiming this weekend after the saved date passes and hides invalid dates", () => {
  const view = render(<HeroCountdown targetDate="2026-10-06" />);
  act(() => jest.advanceTimersByTime(0));
  expect(screen.getByText("in 1d 0h")).toBeVisible();
  act(() => jest.advanceTimersByTime(24 * 60 * 60 * 1000));
  expect(screen.getByText("Scheduled date passed")).toBeVisible();
  expect(screen.queryByText("this weekend")).not.toBeInTheDocument();
  view.rerender(<HeroCountdown targetDate="unknown" />);
  act(() => jest.advanceTimersByTime(0));
  expect(view.container).toBeEmptyDOMElement();
});
