import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import CircuitExplorer from "@/components/ui/CircuitExplorer";
import { loadSchematic, type VerifiedSchematic } from "@/lib/circuitExplorer";
import { review, schematic } from "@/test-support/circuitExplorer";

jest.mock("@/lib/circuitExplorer", () => ({ ...jest.requireActual("@/lib/circuitExplorer"), loadSchematic: jest.fn() }));
let reduced = false;
jest.mock("@/lib/useReducedMotion", () => ({ useReducedMotion: () => reduced }));
let visibility: IntersectionObserverCallback;
const originalObserver = globalThis.IntersectionObserver;
let assets: VerifiedSchematic[];
function verified() {
  const result = { schematic, imageUrl: `blob:qa-verified-${assets.length}`, release: jest.fn() };
  assets.push(result); return result;
}
beforeEach(() => {
  reduced = false; assets = [];
  (loadSchematic as jest.Mock).mockReset().mockImplementation(async () => verified());
  globalThis.IntersectionObserver = class {
    constructor(callback: IntersectionObserverCallback) { visibility = callback; }
    observe() {} unobserve() {} disconnect() {} takeRecords() { return []; }
    root = null; rootMargin = "0px"; thresholds = [0.15];
  };
});
afterEach(() => { globalThis.IntersectionObserver = originalObserver; jest.useRealTimers(); });
async function open() {
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ }));
  await imageLoaded();
}
async function imageLoaded() {
  const image = await screen.findByRole("img", { name: /circuit schematic/ });
  Object.defineProperties(image, { naturalWidth: { value: 12, configurable: true }, naturalHeight: { value: 9, configurable: true } });
  fireEvent.load(image);
  await screen.findByRole("button", { name: "Show Turn 1: QA first" });
}
function visible(value: boolean, ratio = value ? 1 : 0) {
  act(() => visibility([{ isIntersecting: value, intersectionRatio: ratio } as IntersectionObserverEntry], {} as IntersectionObserver));
}

test("unknown coverage creates no launch button or empty panel", () => {
  const { container } = render(<CircuitExplorer review={null} />);
  expect(container).toBeEmptyDOMElement();
  expect(loadSchematic).not.toHaveBeenCalled();
});
test("user intent loads verified bytes; credit remains with the image and closing releases it", async () => {
  render(<CircuitExplorer review={review} />);
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(loadSchematic).not.toHaveBeenCalled();
  await open();
  expect(loadSchematic).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("link", { name: "QA schematic" })).toHaveAttribute("href", schematic.source.page);
  expect(screen.getByRole("link", { name: "CC BY-SA 4.0" })).toHaveAttribute("href", schematic.license.url);
  expect(screen.getByText(/by QA author/)).toHaveTextContent("Resized; three interactive highlights added");
  expect(screen.getByText(/No endorsement/)).toBeVisible();
  expect(screen.getByRole("img")).toHaveAttribute("src", "blob:qa-verified-0");
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ }));
  expect(assets[0].release).toHaveBeenCalledTimes(1);
  await open();
  expect(loadSchematic).toHaveBeenCalledTimes(2);
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
  expect(screen.getByText("First QA highlight.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Tour highlights" })).toHaveAttribute("aria-pressed", "false");
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
  expect(assets[0].release).toHaveBeenCalledTimes(1);
  (loadSchematic as jest.Mock).mockRejectedValueOnce(new Error("unavailable"));
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ }));
  expect(await screen.findByText(/Circuit explorer unavailable/)).toBeVisible();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ })); await open();
});

test("no checked claims, hotspots or tour controls appear before the rendered image loads", async () => {
  render(<CircuitExplorer review={review} />);
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ }));
  await screen.findByRole("img");
  expect(screen.queryByText(/checked against/)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Show Turn/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Tour highlights" })).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Loading circuit schematic");
  await imageLoaded();
  expect(screen.getByText(/checked against/)).toBeVisible();
});
test("a render/decode failure removes all controls and claims; direct retry and reopen both recover", async () => {
  render(<CircuitExplorer review={review} />); await open(); visible(true);
  fireEvent.click(screen.getByRole("button", { name: "Tour highlights" }));
  fireEvent.error(screen.getByRole("img"));
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Show Turn|Tour highlights|Pause tour/ })).not.toBeInTheDocument();
  expect(screen.queryByText(/checked against/)).not.toBeInTheDocument();
  expect(assets[0].release).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Try again" })); await imageLoaded();
  fireEvent.error(screen.getByRole("img"));
  expect(assets[1].release).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ })); await open();
  expect(screen.getByText(/checked against/)).toBeVisible();
});
test("a rendered image with unexpected dimensions is rejected", async () => {
  render(<CircuitExplorer review={review} />);
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ }));
  const image = await screen.findByRole("img");
  Object.defineProperties(image, { naturalWidth: { value: 13 }, naturalHeight: { value: 9 } });
  fireEvent.load(image);
  expect(screen.getByRole("status")).toHaveTextContent("unavailable");
  expect(screen.queryByText(/checked against/)).not.toBeInTheDocument();
  expect(assets[0].release).toHaveBeenCalledTimes(1);
});
test("an image replaced with a mutable path cannot keep checked claims even at matching dimensions", async () => {
  render(<CircuitExplorer review={review} />); await open();
  const image = screen.getByRole("img"); image.setAttribute("src", schematic.asset.path);
  fireEvent.load(image);
  expect(screen.queryByText(/checked against/)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Show Turn|Tour highlights/ })).not.toBeInTheDocument();
  expect(assets[0].release).toHaveBeenCalledTimes(1);
});
test("unmounting releases the ready URL", async () => {
  const { unmount } = render(<CircuitExplorer review={review} />); await open();
  unmount(); expect(assets[0].release).toHaveBeenCalledTimes(1);
});
test("a late load after unmount or close is released instead of displayed", async () => {
  let finish!: (value: VerifiedSchematic) => void;
  (loadSchematic as jest.Mock).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  const { unmount } = render(<CircuitExplorer review={review} />);
  fireEvent.click(screen.getByRole("button", { name: /Explore QA venue/ }));
  const signal = (loadSchematic as jest.Mock).mock.calls[0][2] as AbortSignal;
  unmount(); expect(signal.aborted).toBe(true);
  const late = verified(); await act(async () => finish(late));
  await waitFor(() => expect(late.release).toHaveBeenCalledTimes(1));
  render(<CircuitExplorer review={review} />); await open();
  expect(screen.getByRole("img")).toHaveAttribute("src", "blob:qa-verified-1");
});
