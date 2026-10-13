import { render, screen } from "@testing-library/react";
import ModelHealthPanel from "@/components/accuracy/ModelHealthPanel";
import type { ModelHealthData } from "@/lib/data";

jest.mock("recharts", () => {
  const Box = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;
  return {
    LineChart: Box,
    Line: Box,
    XAxis: Box,
    YAxis: Box,
    CartesianGrid: Box,
    Tooltip: Box,
    ReferenceLine: Box,
    ResponsiveContainer: Box,
  };
});

const available: ModelHealthData = {
  season: 2026,
  diagnosticStatus: "available",
  outputMetric: "rmse_position_error",
  outputUnit: "positions",
  lastEvaluatedRound: 15,
  lastObservedRound: 15,
  rmseByRound: [
    { round: 14, rmse: 3 },
    { round: 15, rmse: 4 },
  ],
  outputDrift: {
    rolling_rmse_recent: 4,
    rolling_rmse_baseline: 3,
    relative_change: 1 / 3,
    severity: "alarm",
    rounds_compared: 10,
  },
};

test("held diagnostics stay compact and hide stale metrics and health claims", () => {
  render(
    <ModelHealthPanel
      health={{
        ...available,
        diagnosticStatus: "publication_hold",
        lastObservedRound: 17,
        unavailableReason: "The latest forecast is withheld.",
      }}
    />,
  );
  expect(screen.getByRole("region", { name: "Model health" })).toBeInTheDocument();
  expect(screen.getByText("Unavailable")).toBeInTheDocument();
  expect(screen.getByText(/forecast is withheld.*Latest elapsed round: R17/)).toBeInTheDocument();
  expect(screen.queryByText("Error increased")).not.toBeInTheDocument();
  expect(screen.queryByText("Error trend")).not.toBeInTheDocument();
  expect(screen.queryByText(/Round by Round/)).not.toBeInTheDocument();
});

test("no eligible forecasts and unlabeled legacy exports are unavailable", () => {
  const { rerender } = render(
    <ModelHealthPanel
      health={{
        season: 2026,
        diagnosticStatus: "no_eligible_rounds",
        unavailableReason: "No eligible settled forecasts.",
      }}
    />,
  );
  expect(screen.getByText("Unavailable")).toBeInTheDocument();
  rerender(<ModelHealthPanel health={{ season: 2026, outputDrift: { severity: "ok" } }} />);
  expect(screen.getByText("Unavailable")).toBeInTheDocument();
  expect(screen.queryByText("Healthy")).not.toBeInTheDocument();
});

test("eligible output is labeled position RMSE in positions and dated to its grade", () => {
  render(<ModelHealthPanel health={available} />);
  expect(screen.getByText("Position RMSE, Round by Round")).toBeInTheDocument();
  expect(
    screen.getByText(/Root mean squared finishing-position error, in positions/),
  ).toBeInTheDocument();
  expect(screen.getByText(/Evaluated through R15/)).toBeInTheDocument();
  expect(screen.getByText(/higher error than the previous rolling window/)).toBeInTheDocument();
  expect(
    screen.queryByText(/Probability Error|calibrated|season benchmark/),
  ).not.toBeInTheDocument();
});

test("insufficient rolling history cannot display healthy", () => {
  render(
    <ModelHealthPanel
      health={{
        ...available,
        outputDrift: {
          severity: "insufficient_history",
          relative_change: null,
          rounds_compared: 2,
        },
      }}
    />,
  );
  expect(screen.getByText("Insufficient history")).toBeInTheDocument();
  expect(screen.getByText("Not enough graded rounds yet.")).toBeInTheDocument();
  expect(screen.queryByText("Healthy")).not.toBeInTheDocument();
});

test("missing health file renders nothing", () => {
  const { container } = render(<ModelHealthPanel health={null} />);
  expect(container).toBeEmptyDOMElement();
});

test("stable relative error describes only the trend", () => {
  render(
    <ModelHealthPanel
      health={{
        ...available,
        outputDrift: { severity: "ok", relative_change: 0, rounds_compared: 10 },
      }}
    />,
  );
  expect(screen.getByText("Stable error trend")).toBeInTheDocument();
  expect(screen.getByText(/same error as the previous rolling window/)).toBeInTheDocument();
  expect(screen.queryByText("Healthy")).not.toBeInTheDocument();
});

test("zero prior error explains unavailable comparison without claiming too few rounds", () => {
  render(
    <ModelHealthPanel
      health={{
        ...available,
        outputDrift: {
          severity: "insufficient_baseline",
          relative_change: null,
          rounds_compared: 10,
        },
      }}
    />,
  );
  expect(screen.getByText("Comparison unavailable")).toBeInTheDocument();
  expect(screen.getByText(/prior window has zero error/)).toBeInTheDocument();
  expect(screen.queryByText("Not enough graded rounds yet.")).not.toBeInTheDocument();
});
