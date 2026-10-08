import { CAPTURE_LIMITS, parseReplayCapture, captureViewport } from "@/lib/replayStream";

// Original synthetic values matching the pinned stream's field names.
const shape = { x: [0, 10, 0], y: [0, 0, 10], rotation_deg: 30 };
const message = (extra = {}) => ({
  frame_index: 8,
  frame: { t: 2.5, drivers: { AAA: { x: 1, y: 2 } } },
  ...extra,
});
test("accepts the documented stream fields; optional channels never become invented values", () => {
  const data = parseReplayCapture(
    JSON.stringify(
      message({
        track_geometry: shape,
        lap_times: { AAA: [{ sector1_s: null }] },
        frame: { t: 2.5, drivers: { AAA: { x: null, y: null } }, safety_car: { x: 50, y: 50 } },
      }),
    ),
    "local.ndjson",
  );
  expect(data.frames[0].drivers[0]).toMatchObject({ name: "Driver AAA", x: null, y: null });
  expect(data.frames[0]).not.toHaveProperty("safety_car");
  expect(data.frames[0]).not.toHaveProperty("lap_times");
  expect(data.source).toBe("local");
});
test("keeps duplicate paused frames and rewinds in received order", () => {
  const data = parseReplayCapture(
    [message(), message(), message({ frame_index: 1, frame: { t: 0, drivers: {} } })]
      .map((value) => JSON.stringify(value))
      .join("\n"),
    "rewind.ndjson",
  );
  expect(data.frames.map((f) => f.index)).toEqual([8, 8, 1]);
  expect(data.frames.map((f) => f.time)).toEqual([2.5, 2.5, 0]);
  expect(data.frames[2].drivers).toEqual([]);
});
test("late and updated geometry applies forward only, without borrowing from future snapshots", () => {
  const updated = { ...shape, x: [100, 110, 100] };
  const data = parseReplayCapture(
    [message(), message({ track_geometry: shape }), message(), message({ track_geometry: updated })]
      .map((value) => JSON.stringify(value))
      .join("\n"),
    "geometry.ndjson",
  );
  expect(data.frames[0].geometry).toBeNull();
  expect(data.frames[1].geometry?.x).toEqual(shape.x);
  expect(data.frames[2].geometry).toBe(data.frames[1].geometry);
  expect(data.frames[3].geometry?.x).toEqual(updated.x);
});
test.each([
  {},
  { frame_index: -1 },
  { frame_index: 2.3 },
  { frame_index: Number.MAX_SAFE_INTEGER + 1, frame: { t: 0, drivers: {} } },
  { frame: { t: -1, drivers: {} } },
  { frame: { t: 0, drivers: { AAA: { x: null, y: 2 } } } },
  { frame: { t: 0, drivers: { AAA: { x: 1e20, y: 2 } } } },
])("rejects malformed or unsafe message %j", (invalid) => {
  expect(() => parseReplayCapture(JSON.stringify(invalid), "bad.ndjson")).toThrow();
});
test.each([
  { ...shape, y: [1] },
  { ...shape, rotation_deg: 999 },
  { ...shape, x: [1, 1, 1] },
])("rejects unusable track shape %j", (invalid) => {
  expect(() =>
    parseReplayCapture(JSON.stringify(message({ track_geometry: invalid })), "bad.ndjson"),
  ).toThrow(/Track/);
});
test("reports broken JSON and bounded UTF-8 size/frame/point counts", () => {
  expect(() => parseReplayCapture("{", "bad.json")).toThrow(/Snapshot 1/);
  expect(() => parseReplayCapture("é".repeat(CAPTURE_LIMITS.bytes / 2 + 1), "huge.json")).toThrow(
    /4 MiB/,
  );
  expect(() =>
    parseReplayCapture(
      Array(CAPTURE_LIMITS.frames + 1)
        .fill(JSON.stringify(message()))
        .join("\n"),
      "many.jsonl",
    ),
  ).toThrow(/2000/);
  expect(() =>
    parseReplayCapture(
      JSON.stringify(
        message({ track_geometry: { x: Array(4097).fill(0), y: Array(4097).fill(0) } }),
      ),
      "many.json",
    ),
  ).toThrow(/4096/);
});
test("ignores untrusted colors and renders names as bounded text data", () => {
  const data = parseReplayCapture(
    JSON.stringify(
      message({
        driver_colors: { AAA: "url(https://untrusted.invalid)" },
        frame: { t: 0, drivers: { AAA: { x: 0, y: 0, name: "<script>bad</script>" } } },
      }),
    ),
    "local.json",
  );
  expect(data.frames[0].drivers[0].color).toBe("var(--ink)");
  expect(data.frames[0].drivers[0].name).toBe("<script>bad</script>");
});
test("native SVG viewport includes the whole rotated coordinate set", () => {
  const view = captureViewport({ x: shape.x, y: shape.y, rotation: 30 });
  expect(view.radius).toBeGreaterThan(Math.hypot(5, 5));
  expect(view.viewBox).not.toMatch(/NaN|Infinity/);
});

const fastf1Message = () =>
  message({
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
          x: null,
          y: null,
          sample_source: "car",
          telemetry: { speed_kph: 123, rpm: 9000, throttle_pct: 0, gear: 0, brake: false },
        },
      },
    },
  });
test("local FastF1 metadata keeps units, session time and honest optional channels", () => {
  const parsed = parseReplayCapture(JSON.stringify(fastf1Message()), "synthetic.ndjson");
  expect(parsed.fastf1).toEqual({ season: 2025, round: 1, session: "Race", version: "synthetic" });
  expect(parsed.frames[0].time).toBe(100);
  expect(parsed.frames[0].geometry).toBeNull();
  expect(parsed.frames[0].drivers[0]).toMatchObject({
    sampleSource: "car",
    x: null,
    telemetry: { throttle_pct: 0, gear: 0, brake: false },
  });
});
test.each([
  "Formula 2",
  "Formula 3",
  "Formula E",
  "IndyCar",
  "NASCAR",
  "MotoGP",
  "WRC",
  "WEC",
  "IMSA",
  "Le Mans",
])("F1-only input is explicitly unsupported in %s", (series) => {
  expect(() =>
    parseReplayCapture(JSON.stringify(fastf1Message()), "synthetic.ndjson", series),
  ).toThrow(`unsupported in ${series}`);
});
test("wrong units, time basis, late metadata and malformed brake fail closed", () => {
  const fixture = JSON.parse(JSON.stringify(fastf1Message()));
  for (const field of ["coordinate_units", "time_basis", "data_rights"]) {
    expect(() =>
      parseReplayCapture(
        JSON.stringify({
          ...fixture,
          capture_metadata: { ...fixture.capture_metadata, [field]: "incorrect" },
        }),
        "bad.ndjson",
      ),
    ).toThrow(/metadata/);
  }
  expect(() =>
    parseReplayCapture(
      [JSON.stringify(message()), JSON.stringify(fixture)].join("\n"),
      "late.ndjson",
    ),
  ).toThrow(/metadata/);
  fixture.frame.drivers.AAA.telemetry.brake = 50;
  expect(() => parseReplayCapture(JSON.stringify(fixture), "brake.ndjson")).toThrow(/telemetry/);
});
