import { act, fireEvent, render, screen } from "@testing-library/react";
import CircuitReplayWorkspace from "@/components/ui/CircuitReplayWorkspace";
let reduced = false;
jest.mock("@/lib/useReducedMotion", () => ({ useReducedMotion: () => reduced }));
beforeEach(() => {
  reduced = false;
});
const payload = JSON.stringify({
  frame_index: 1,
  frame: { t: 0, drivers: { AAA: { x: 1, y: 2 } } },
  track_geometry: { x: [0, 10, 0], y: [0, 0, 10] },
});
const file = (text: Promise<string>, name = "own-capture.ndjson") => ({
  name,
  size: 1024,
  text: () => text,
});
function upload(value: unknown) {
  fireEvent.change(screen.getByLabelText("Open local capture", { selector: "input" }), {
    target: { files: [value] },
  });
}
test("starts with truthful unavailable coverage and no telemetry fetch or invented map", () => {
  render(<CircuitReplayWorkspace />);
  expect(screen.getByText("Circuit map unavailable")).toBeVisible();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.getByRole("combobox")).toHaveValue("Formula 1");
});
test("user import renders processed positions, with provenance visibly unverified", async () => {
  render(<CircuitReplayWorkspace />);
  upload(file(Promise.resolve(payload)));
  expect(await screen.findByText("Local capture · Source and layout unverified")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: /Driver AAA/ }));
  expect(screen.getByRole("button", { name: /Driver AAA/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByText("Full name not supplied")).toBeVisible();
});
test("series change clears positions and cancels a pending read", async () => {
  let resolve!: (s: string) => void;
  const pending = new Promise<string>((r) => {
    resolve = r;
  });
  render(<CircuitReplayWorkspace />);
  upload(file(pending));
  expect(screen.getByRole("status", { name: "" })).toHaveTextContent("Opening capture");
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "WRC" } });
  await act(async () => resolve(payload));
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.queryByText("own-capture.ndjson")).not.toBeInTheDocument();
});
test("late import cannot replace a newer source and repeated filenames can be retried", async () => {
  let resolve!: (s: string) => void;
  render(<CircuitReplayWorkspace />);
  upload(
    file(
      new Promise<string>((r) => {
        resolve = r;
      }),
    ),
  );
  upload(file(Promise.resolve(payload), "second.ndjson"));
  await screen.findByText("second.ndjson");
  await act(async () => resolve(payload));
  expect(screen.queryByText("own-capture.ndjson")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Clear capture" }));
  upload(file(Promise.resolve(payload), "second.ndjson"));
  expect(await screen.findByText("second.ndjson")).toBeVisible();
});
test("invalid input clears stale data, exposes a recovery action, and never executes pickle", async () => {
  render(<CircuitReplayWorkspace />);
  upload(file(Promise.resolve(payload)));
  await screen.findByRole("img");
  upload(file(Promise.resolve("bad"), "cache.pkl"));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Choose a JSON, JSONL or NDJSON capture",
  );
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Choose another capture" })).toBeVisible();
});
test("reduced-motion imports remain static until explicit snapshot selection", async () => {
  reduced = true;
  const { container } = render(<CircuitReplayWorkspace />);
  upload(file(Promise.resolve(payload)));
  await screen.findByRole("img");
  expect(container.querySelector('[data-motion="reduced-static"]')).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /play|auto|tour/i })).not.toBeInTheDocument();
});
