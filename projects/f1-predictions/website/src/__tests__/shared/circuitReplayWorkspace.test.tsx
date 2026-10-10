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
  fireEvent.click(screen.getByRole("button", { name: /^Driver AAA/ }));
  expect(screen.getByRole("button", { name: /^Driver AAA/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByText("Full name not supplied")).toBeVisible();
});
test("map and list share selection, toggle off and offer a visible clear action", async () => {
  render(<CircuitReplayWorkspace />);
  upload(file(Promise.resolve(payload)));
  const marker = await screen.findByRole("button", { name: "Select Driver AAA on circuit" });
  const list = screen.getByRole("button", { name: /^Driver AAA/ });
  fireEvent.click(marker);
  expect(marker).toHaveAttribute("aria-pressed", "true");
  expect(list).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByLabelText("Map selection")).toHaveTextContent("Driver AAA");
  fireEvent.click(list);
  expect(marker).toHaveAttribute("aria-pressed", "false");
  fireEvent.click(list);
  const clear = screen.getByRole("button", { name: "Clear driver selection" });
  clear.focus();
  fireEvent.click(clear);
  expect(marker).toHaveFocus();
  expect(list).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByLabelText("Map selection")).toHaveTextContent("Tap a marker");
});
test("missing, off-map and absent samples stay truthful while retaining list access", async () => {
  const frames = [
    JSON.parse(payload),
    {
      frame_index: 2,
      frame: { t: 1, drivers: { AAA: { x: null, y: null }, BBB: { x: 1000, y: 1000 } } },
    },
    { frame_index: 3, frame: { t: 2, drivers: {} } },
  ];
  render(<CircuitReplayWorkspace />);
  upload(file(Promise.resolve(frames.map((frame) => JSON.stringify(frame)).join("\n"))));
  fireEvent.click(await screen.findByRole("button", { name: "Select Driver AAA on circuit" }));
  fireEvent.click(screen.getByRole("button", { name: "Next snapshot" }));
  expect(screen.queryByRole("button", { name: /on circuit$/ })).not.toBeInTheDocument();
  expect(screen.getByLabelText("Map selection")).toHaveTextContent("Position unavailable");
  fireEvent.click(screen.getByRole("button", { name: /^Driver BBB/ }));
  expect(screen.getByLabelText("Map selection")).toHaveTextContent("outside this map view");
  fireEvent.click(screen.getByRole("button", { name: "Next snapshot" }));
  expect(screen.getByLabelText("Map selection")).toHaveTextContent("absent");
  const clear = screen.getByRole("button", { name: "Clear driver selection" });
  clear.focus();
  fireEvent.click(clear);
  expect(screen.getByLabelText("Map selection")).toHaveFocus();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "IndyCar" } });
  expect(screen.queryByLabelText("Map selection")).not.toBeInTheDocument();
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

const syntheticFastF1 = JSON.stringify({
  frame_index: 0,
  capture_metadata: {
    provider: "FastF1",
    schema_version: 1,
    series: "Formula 1",
    season: 2025,
    round: 1,
    session: "Race",
    software_version: "synthetic",
    time_basis: "session-relative-seconds",
    coordinate_units: "metres",
    sampling: "native-independent",
    data_rights: "not-certified",
  },
  frame: {
    t: 100,
    drivers: {
      AAA: {
        name: "Original Sample Driver",
        x: null,
        y: null,
        sample_source: "car",
        telemetry: { speed_kph: 123, rpm: 9000, throttle_pct: 0, gear: 0, brake: false },
      },
    },
  },
});
test("FastF1 input shows provenance, native channels and boolean brake without an invented map", async () => {
  render(<CircuitReplayWorkspace />);
  upload(file(Promise.resolve(syntheticFastF1), "synthetic-fastf1.ndjson"));
  expect(await screen.findByText("Local FastF1 capture · Unverified samples")).toBeVisible();
  expect(screen.getByLabelText("Capture provenance")).toHaveTextContent("not exact coordinates");
  fireEvent.click(screen.getByRole("button", { name: "Original Sample Driver" }));
  expect(screen.getByText("123 km/h")).toBeVisible();
  expect(screen.getByText("Brake applied").nextSibling).toHaveTextContent("No");
  expect(screen.getByText("Circuit map unavailable")).toBeVisible();
});
test("a non-F1 selection rejects the same capture and offers recovery", async () => {
  render(<CircuitReplayWorkspace />);
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "WRC" } });
  upload(file(Promise.resolve(syntheticFastF1)));
  expect(await screen.findByRole("alert")).toHaveTextContent("unsupported in WRC");
  expect(screen.queryByText("123 km/h")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Choose another capture" })).toBeVisible();
});
