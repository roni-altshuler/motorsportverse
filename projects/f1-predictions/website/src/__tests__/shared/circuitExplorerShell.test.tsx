import { act, fireEvent, render, screen } from "@testing-library/react";
import CircuitExplorer from "@/components/ui/CircuitExplorer";
import { loadSchematic } from "@/lib/circuitExplorer";
import { review, schematic } from "@/test-support/circuitExplorer";

jest.mock("@/lib/circuitExplorer", () => ({ ...jest.requireActual("@/lib/circuitExplorer"), loadSchematic: jest.fn() }));
let reduced = false;
jest.mock("@/lib/useReducedMotion", () => ({ useReducedMotion: () => reduced }));
let visibility: IntersectionObserverCallback;
const originalObserver = globalThis.IntersectionObserver;
beforeEach(() => {
  reduced = false;
  (loadSchematic as jest.Mock).mockReset().mockResolvedValue(schematic);
  globalThis.IntersectionObserver = class {
    constructor(callback: IntersectionObserverCallback) { visibility = callback; }
    observe() {} unobserve() {} disconnect() {} takeRecords() { return []; }
    root = null; rootMargin = "0px"; thresholds = [0.15];
  };
});
afterEach(() => { globalThis.IntersectionObserver = originalObserver; jest.useRealTimers(); });
async function open() {
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ }));
  await screen.findByRole("img", { name: /circuit schematic/ });
}
function visible(value: boolean, ratio = value ? 1 : 0) {
  act(() => visibility([{ isIntersecting: value, intersectionRatio: ratio } as IntersectionObserverEntry], {} as IntersectionObserver));
}

test("unknown coverage creates no launch button or empty panel", () => {
  const { container } = render(<CircuitExplorer review={null} />);
  expect(container).toBeEmptyDOMElement();
  expect(loadSchematic).not.toHaveBeenCalled();
});
test("user intent loads once; credit/license/modification notice remain with the artwork", async () => {
  render(<CircuitExplorer review={review} />);
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(loadSchematic).not.toHaveBeenCalled();
  await open();
  expect(loadSchematic).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("link", { name: "QA schematic" })).toHaveAttribute("href", schematic.source.page);
  expect(screen.getByRole("link", { name: "CC BY-SA 4.0" })).toHaveAttribute("href", schematic.license.url);
  expect(screen.getByText(/by QA author/)).toHaveTextContent("Resized; three interactive highlights added");
  expect(screen.getByText(/No endorsement/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ }));
  await open();
  expect(loadSchematic).toHaveBeenCalledTimes(1);
});
test("map arrows/Home/End and the list select the same corner", async () => {
  render(<CircuitExplorer review={review} />); await open();
  const first = screen.getByRole("button", { name: "Show Turn 1: QA first" });
  first.focus(); fireEvent.keyDown(first, { key: "ArrowRight" });
  expect(screen.getByRole("button", { name: "Show Turn 3: QA middle" })).toHaveFocus();
  expect(screen.getByText("Middle QA highlight.")).toBeVisible();
  fireEvent.keyDown(document.activeElement!, { key: "End" });
  expect(screen.getByText("Final QA highlight.")).toBeVisible();
  fireEvent.keyDown(document.activeElement!, { key: "Home" });
  expect(first).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "T03 QA middle" }));
  expect(screen.getByText("Middle QA highlight.")).toBeVisible();
});
test("the optional tour pauses offscreen, while hidden and when closed", async () => {
  jest.useFakeTimers(); render(<CircuitExplorer review={review} />); await open(); visible(true);
  fireEvent.click(screen.getByRole("button", { name: "Tour highlights" }));
  act(() => jest.advanceTimersByTime(6000));
  expect(screen.getByText("Middle QA highlight.")).toBeVisible();
  visible(true, 0.01); act(() => jest.advanceTimersByTime(12000));
  expect(screen.getByText("Middle QA highlight.")).toBeVisible();
  visible(false); act(() => jest.advanceTimersByTime(12000));
  expect(screen.getByText("Middle QA highlight.")).toBeVisible();
  visible(true);
  const hidden = Object.getOwnPropertyDescriptor(document, "hidden");
  Object.defineProperty(document, "hidden", { value: true, configurable: true });
  fireEvent(document, new Event("visibilitychange")); act(() => jest.advanceTimersByTime(12000));
  expect(screen.getByText("Middle QA highlight.")).toBeVisible();
  if (hidden) Object.defineProperty(document, "hidden", hidden); else delete (document as unknown as Record<string, unknown>).hidden;
  fireEvent(document, new Event("visibilitychange"));
  act(() => jest.advanceTimersByTime(6000)); expect(screen.getByText("Final QA highlight.")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ }));
  act(() => jest.advanceTimersByTime(12000)); await open();
  expect(screen.getByText("Final QA highlight.")).toBeVisible();
});
test("reduced motion keeps manual controls and offers no automatic tour", async () => {
  reduced = true; render(<CircuitExplorer review={review} />); await open();
  expect(screen.queryByRole("button", { name: /Tour highlights/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Show Turn 14: QA final" }));
  expect(screen.getByText("Final QA highlight.")).toBeVisible();
});
test("an event change drops the old image; failed loading is truthful and retryable", async () => {
  const { rerender } = render(<CircuitExplorer review={review} />); await open();
  rerender(<CircuitExplorer review={{ ...review, event: { ...review.event, season: 2025 } }} />);
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  (loadSchematic as jest.Mock).mockRejectedValueOnce(new Error("unavailable"));
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ }));
  expect(await screen.findByText(/Circuit explorer unavailable/)).toBeVisible();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ })); await open();
});
