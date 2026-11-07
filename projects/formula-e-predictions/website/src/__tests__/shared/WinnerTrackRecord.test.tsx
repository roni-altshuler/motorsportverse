import { act, fireEvent, render, screen } from "@testing-library/react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import WinnerTrackRecord from "@/components/ui/WinnerTrackRecord";
import type { TrackRecordData, WinnerRecord } from "@/lib/trackRecord";

let chartWidth = 650;
let resizeChart: () => void;
beforeEach(() => {
  chartWidth = 650;
  jest.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(() => ({ width: chartWidth } as DOMRect));
  global.ResizeObserver = class {
    constructor(callback: () => void) { resizeChart = callback; }
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
});
afterEach(() => jest.restoreAllMocks());

function row(round: number, correct: boolean, extra: Partial<WinnerRecord> = {}): WinnerRecord {
  return { id: `fixture:2026:${round}:race`, season: 2026, round, scope: "race", scopeLabel: "Race", event: `Fixture race ${round}`, date: `2026-01-${String(round).padStart(2, "0")}`,
    predictedWinner: "A", actualWinner: correct ? "A" : "B", correct, status: "scored", reason: "Explicit test-only verified record", modelVersion: round === 2 ? "recorded-test-version" : null,
    savedComparison: { predictedWinner: "A", actualWinner: correct ? "A" : "B", correct, status: "compared", reason: "Explicit test-only saved comparison", modelVersion: round === 2 ? "recorded-test-version" : null, positions: [{ id: "A", name: "Driver A", predicted: 1, actual: correct ? 1 : 2 }] },
    source: "fixture.json", publication: null, forecastSource: null, forecastSha256: null, publicationEvent: null, sourceCommit: null, positions: [{ id: "A", name: "Driver A", predicted: 1, actual: correct ? 1 : 2 }], ...extra };
}
const data = (records: WinnerRecord[]): TrackRecordData => ({ series: "f2", label: "Formula 2", currentSeason: 2026, asOf: "2026-01-30", evaluationBasis: "walk_forward_replay", records });
it("shows Not yet scored rather than 0% for unverified saved records", () => {
  render(<WinnerTrackRecord data={data([row(1, true, { status: "unverified", correct: null })])} season={2026} onSeasonChange={jest.fn()} />);
  fireEvent.change(screen.getByRole("combobox", { name: "Record basis" }), { target: { value: "verified" } });
  expect(screen.getByTestId("winner-headline")).toHaveTextContent("Not yet scored");
  expect(screen.queryByRole("slider")).not.toBeInTheDocument();
  expect(screen.getByText(/F2’s walk-forward evaluation/)).toBeInTheDocument();
  expect(screen.getAllByTestId("winner-record")).toHaveLength(1);
});
it("reconciles headline, timeline detail and every pick, with touch/keyboard date selection", () => {
  render(<WinnerTrackRecord data={data([row(1, true), row(2, false), row(3, true)])} season={2026} onSeasonChange={jest.fn()} />);
  expect(screen.getByTestId("winner-headline")).toHaveTextContent("66.7%");
  expect(screen.getByText("2 winner matches / 3 settled comparisons")).toBeInTheDocument();
  expect(screen.getAllByTestId("winner-record")).toHaveLength(3);
  expect(screen.getByTestId("point-detail")).toHaveTextContent("Cumulative 2/3");
  fireEvent.change(screen.getByRole("slider"), { target: { value: "1" } });
  expect(screen.getByTestId("point-detail")).toHaveTextContent("Cumulative 1/2");
  expect(screen.getByRole("table", { name: /Cumulative and rolling/ })).toBeInTheDocument();
  expect(screen.getByText("recorded-test-version")).toBeInTheDocument();
});
it("keeps axis text readable when the chart container becomes phone-sized", () => {
  render(<WinnerTrackRecord data={data([row(1, true), row(2, false), row(3, true)])} season={2026} onSeasonChange={jest.fn()} />);
  const chart = screen.getByRole("img", { name: /winner matches by event date/ });
  expect(chart).toHaveAttribute("viewBox", "0 0 650 290");
  chartWidth = 256;
  act(() => resizeChart());
  expect(chart).toHaveAttribute("viewBox", "0 0 256 290");
  expect(chart.querySelectorAll('text[y="274"]')).toHaveLength(2);
  expect(chart.querySelector('text[text-anchor="end"]')).toHaveAttribute("font-size", "13");
  chartWidth = 800;
  act(() => resizeChart());
  expect(chart).toHaveAttribute("viewBox", "0 0 800 290");
  expect(chart.querySelectorAll('text[y="274"]')).toHaveLength(3);
});
it("hydrates populated SVG tooltip titles without replacing the server-rendered chart", async () => {
  const ui = <WinnerTrackRecord data={data([row(1, true), row(2, false)])} season={2026} onSeasonChange={jest.fn()} />;
  const errors: unknown[] = [];
  const container = document.createElement("div");
  container.innerHTML = renderToString(ui);
  document.body.appendChild(container);
  const serverChart = container.querySelector("svg");
  let root: ReturnType<typeof hydrateRoot>;
  await act(async () => { root = hydrateRoot(container, ui, { onRecoverableError: error => errors.push(error) }); });
  expect(errors).toEqual([]);
  expect(container.querySelector("svg")).toBe(serverChart);
  expect(container.querySelector("circle title")?.textContent).toContain("1/1 cumulative");
  await act(async () => root.unmount());
  container.remove();
});

it("changes the whole record basis without promoting historical matches into pre-race accuracy", () => {
  const original = row(1, true);
  original.savedComparison = { ...original.savedComparison!, predictedWinner: "B", correct: false,
    positions: [{ id: "B", name: "Driver B", predicted: 1, actual: 2 }, { id: "A", name: "Driver A", predicted: 2, actual: 1 }] };
  render(<WinnerTrackRecord data={data([original])} season={2026} onSeasonChange={jest.fn()} />);
  expect(screen.getByTestId("winner-headline")).toHaveTextContent("0.0%");
  expect(screen.getByText("Different winner")).toBeInTheDocument();
  expect(screen.getByText("Saved winner pick")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Record basis" }), { target: { value: "verified" } });
  expect(screen.getByTestId("winner-headline")).toHaveTextContent("100.0%");
  expect(screen.getByText("Correct")).toBeInTheDocument();
  expect(screen.getByText("Original model winner pick")).toBeInTheDocument();
  expect(screen.queryByText("Driver B")).not.toBeInTheDocument();
});

it("discloses the dated subset separately from eligible undated comparisons", () => {
  const undated = row(1, true, { date: null, status: "incomplete", correct: null });
  const dated = row(2, false, { status: "unverified", correct: null });
  render(<WinnerTrackRecord data={data([undated, dated])} season={2026} onSeasonChange={jest.fn()} />);
  expect(screen.getByTestId("winner-headline")).toHaveTextContent("50.0%");
  expect(screen.getByTestId("dated-coverage")).toHaveTextContent("1 dated of 2 eligible comparisons · 1 undated");
  expect(screen.getByTestId("point-detail")).toHaveTextContent("Cumulative 0/1");
  expect(screen.getByText("Winner match")).toBeInTheDocument();
  expect(screen.queryByText("Incomplete record")).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("combobox", { name: "Record basis" }), { target: { value: "verified" } });
  expect(screen.getByTestId("winner-headline")).toHaveTextContent("Not yet scored");
  expect(screen.queryByRole("slider")).not.toBeInTheDocument();
});

it("keeps the historical tally visible when all eligible events lack dates", () => {
  render(<WinnerTrackRecord data={data([row(1, true, { date: null, status: "incomplete", correct: null })])} season={2026} onSeasonChange={jest.fn()} />);
  expect(screen.getByTestId("winner-headline")).toHaveTextContent("100.0%");
  expect(screen.getByTestId("dated-coverage")).toHaveTextContent("0 dated of 1 eligible comparisons · 1 undated");
  expect(screen.getByText(/no recorded event dates/)).toBeInTheDocument();
  expect(screen.queryByRole("slider")).not.toBeInTheDocument();
});

it("does not display a held record as a winner match even if comparison metadata is stale", () => {
  render(<WinnerTrackRecord data={data([row(1, true, { status: "held", correct: null, reason: "Explicit publication hold" })])} season={2026} onSeasonChange={jest.fn()} />);
  expect(screen.getByTestId("winner-headline")).toHaveTextContent("No settled comparisons");
  expect(screen.getByText("Withheld")).toBeInTheDocument();
  expect(screen.queryByText("Winner match")).not.toBeInTheDocument();
  expect(screen.getByText(/1 withheld/)).toBeInTheDocument();
});
