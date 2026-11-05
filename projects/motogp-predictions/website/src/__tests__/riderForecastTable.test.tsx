import { fireEvent, render, screen, within } from "@testing-library/react";

import RiderForecastTable from "@/components/race-detail/RiderForecastTable";
import type { ClassificationEntry, RaceBlock } from "@/types/motogp";

jest.mock("@/components/ui/DriverHeadshot", () => ({ DriverHeadshot: () => null }));

// Synthetic UI fixtures, not published forecasts or official race results.
function entry(overrides: Partial<ClassificationEntry>): ClassificationEntry {
  return {
    position: 1, code: "AAA", name: "Rider", team: "Ducati", teamColor: "#c8102e",
    predictedValue: 100, pWin: 0.15, pPodium: 0.78, pTop6: 0.9, pTop10: 0.95,
    meanFinish: 4, finishRangeLow: 1, finishRangeHigh: 12, confidence: "medium",
    headshotUrl: "", actualPosition: null,
    ...overrides,
  };
}

function race(): RaceBlock {
  return {
    raceType: "feature",
    grid: [],
    classification: [
      entry({ position: 1, code: "MAA", name: "Álex Márquez" }),
      entry({ position: 2, code: "MAM", name: "Marc Marquez", pWin: 0.31, pPodium: 0.62, actualPosition: 3 }),
      entry({ position: 3, code: "ACO", name: "Pedro Acosta", team: "KTM", pWin: 0.28, pPodium: 0.88 }),
    ],
  };
}

function riderRows(): HTMLElement[] {
  return screen.getAllByRole("row").slice(1);
}

function displayedRiders(): string[] {
  return riderRows().map((row) => within(row).getByRole("button").getAttribute("aria-label")!);
}

test("search ignores case and accents, combines with manufacturer, and reset restores focus", () => {
  render(<RiderForecastTable block={race()} completed={false} onSelect={jest.fn()} />);
  const search = screen.getByRole("searchbox", { name: "Find a rider" });
  fireEvent.change(search, { target: { value: "aLeX" } });
  expect(screen.getByRole("status")).toHaveTextContent("Showing 1 of 3 riders · Grand Prix");
  expect(displayedRiders()).toEqual(["Open Álex Márquez forecast detail"]);

  fireEvent.change(screen.getByLabelText("Manufacturer"), { target: { value: "KTM" } });
  expect(screen.getByRole("status")).toHaveTextContent("Showing 0 of 3 riders");
  expect(screen.getByText("No riders match these filters.")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Reset filters" }));
  expect(search).toHaveFocus();
  expect(search).toHaveValue("");
  expect(screen.getByLabelText("Manufacturer")).toHaveValue("");
  expect(screen.getByRole("status")).toHaveTextContent("Showing 3 of 3 riders");

  fireEvent.change(search, { target: { value: " ACO " } });
  expect(displayedRiders()).toEqual(["Open Pedro Acosta forecast detail"]);
});

test("win and podium sorting preserve the original forecast positions and input artifacts", () => {
  const block = race();
  const original = JSON.stringify(block);
  block.classification.forEach(Object.freeze);
  Object.freeze(block.classification);
  const onSelect = jest.fn();
  render(<RiderForecastTable block={block} completed onSelect={onSelect} />);

  fireEvent.change(screen.getByLabelText("Sort riders by"), { target: { value: "pWin" } });
  expect(displayedRiders()).toEqual([
    "Open Marc Marquez forecast detail", "Open Pedro Acosta forecast detail", "Open Álex Márquez forecast detail",
  ]);
  expect(within(riderRows()[0]).getAllByRole("cell")[0]).toHaveTextContent("2");
  expect(within(riderRows()[0]).getAllByRole("cell").at(-1)).toHaveTextContent("P3");

  fireEvent.change(screen.getByLabelText("Sort riders by"), { target: { value: "pPodium" } });
  expect(displayedRiders()[0]).toBe("Open Pedro Acosta forecast detail");
  expect(within(riderRows()[0]).getAllByRole("cell").at(-1)).toHaveTextContent("—");
  expect(JSON.stringify(block)).toBe(original);
  fireEvent.click(screen.getByRole("button", { name: "Open Pedro Acosta forecast detail" }));
  expect(onSelect).toHaveBeenCalledTimes(1);
  expect(onSelect).toHaveBeenCalledWith("ACO");
});

test("switching session retains rider filters and reads that session's probabilities", () => {
  const block = race();
  const view = render(<RiderForecastTable block={block} completed={false} onSelect={jest.fn()} />);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "MAA" } });
  expect(screen.getByText("Win 15.0%")).toBeInTheDocument();
  expect(screen.getByText("Podium 78.0%")).toBeInTheDocument();
  view.rerender(<RiderForecastTable block={{
    ...block,
    raceType: "sprint",
    classification: block.classification.map((rider) => ({ ...rider, pWin: 0.12, pPodium: 0.7 })),
  }} completed={false} onSelect={jest.fn()} />);
  expect(screen.getByRole("table", { name: "Sprint rider forecasts" })).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Showing 1 of 3 riders · Sprint");
  expect(screen.getByText("Win 12.0%")).toBeInTheDocument();
  expect(screen.getByText("Podium 70.0%")).toBeInTheDocument();
  expect(screen.queryByRole("columnheader", { name: "Actual" })).not.toBeInTheDocument();
});
