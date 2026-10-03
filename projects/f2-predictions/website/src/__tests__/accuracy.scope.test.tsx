import "@testing-library/jest-dom";
import { render, screen, within } from "@testing-library/react";

import AccuracyPage from "@/app/accuracy/page";
import { getForwardEvalRounds, getForwardEvalSeason } from "@/lib/f2data";

jest.mock("@/lib/f2data", () => ({
  getF2Data: () => ({ season: 2026, completedRounds: 1, totalRounds: 14 }),
  getForwardEvalRounds: jest.fn(),
  getForwardEvalSeason: jest.fn(),
  getModelHealth: () => null,
  getCalibrationSummary: () => null,
  getPromotionStatus: () => null,
  getHistoricalBacktest: () => null,
}));
jest.mock("@/lib/evidence", () => ({ getEvidence: () => null }));
jest.mock("@/components/ui/EvidencePanel", () => ({ EvidencePanel: () => null }));
jest.mock("@/components/ShareButton", () => () => null);
jest.mock("@/components/accuracy/RoundsHeatmap", () => () => null);
jest.mock("@/components/accuracy/WalkForwardPanel", () => () => null);
jest.mock("@/components/accuracy/CandidateModelCard", () => () => null);
jest.mock("@/components/accuracy/CalibrationPanel", () => () => null);
jest.mock("@/components/accuracy/HistoricalBacktestPanel", () => () => null);

const season = {
  season: 2026, roundsScored: 1, meanPositionError: 1, meanNdcgAt5: 0.9,
  winnerHitRate: 1, podiumHitRate: 1, finishersOnly: true,
};
const accuracy = { n: 20, mean_position_error: 1, winner_hit: true, podium_hits: 3 };
const round = { round: 1, venueName: "Test circuit", sprint: accuracy, feature: accuracy,
  markets: { feature: { win: { brier: 0.12, logLoss: 0.3 } } } };

beforeEach(() => {
  jest.mocked(getForwardEvalSeason).mockReturnValue(season);
  jest.mocked(getForwardEvalRounds).mockReturnValue([round]);
});

it("keeps legacy probability scores labeled finishers-only without inventing a sample count", () => {
  render(<AccuracyPage />);
  const scope = screen.getByRole("region", { name: "Scoring scope" });
  expect(within(scope).getByText("Finishers only (legacy artifact)")).toBeInTheDocument();
  expect(within(scope).getByText(/publication timing are not recorded/)).toBeInTheDocument();
  expect(screen.getByText("Sample count not recorded")).toBeInTheDocument();
  expect(screen.getByText("n=20 ranked")).toBeInTheDocument();
});

it("labels regenerated probability scores and replay basis separately from positional scoring", () => {
  jest.mocked(getForwardEvalSeason).mockReturnValue({ ...season,
    marketScope: "reported entrants including DNF/DNS; absent results excluded",
    basis: "walk_forward_replay" });
  jest.mocked(getForwardEvalRounds).mockReturnValue([{ ...round,
    markets: { feature: { win: { ...round.markets.feature.win, n: 22 } } } }]);
  render(<AccuracyPage />);
  const scope = screen.getByRole("region", { name: "Scoring scope" });
  expect(within(scope).getByText("Ranked finishers only")).toBeInTheDocument();
  expect(within(scope).getByText(/reported entrants including DNF\/DNS/)).toBeInTheDocument();
  expect(within(scope).getByText(/Retrospective walk-forward replay/)).toBeInTheDocument();
  expect(screen.getByText("n=22 entrants")).toBeInTheDocument();
  expect(screen.queryByText(/Every number is scored finishers-only/)).not.toBeInTheDocument();
});

it("does not infer probability scope when the season metadata is missing", () => {
  jest.mocked(getForwardEvalSeason).mockReturnValue(null);
  render(<AccuracyPage />);
  expect(within(screen.getByRole("region", { name: "Scoring scope" })).getByText("Scope not recorded")).toBeInTheDocument();
});

it("shows an explicitly empty probability sample without inventing a zero Brier", () => {
  jest.mocked(getForwardEvalRounds).mockReturnValue([{ ...round,
    markets: { feature: { win: { brier: null, logLoss: null, n: 0 } } } }]);
  render(<AccuracyPage />);
  expect(screen.getByText("n=0 entrants")).toBeInTheDocument();
  expect(screen.queryByText("0.0000")).not.toBeInTheDocument();
});
