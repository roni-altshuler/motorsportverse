import { fetchRoundData } from "@/lib/data";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { SeasonData } from "@/types";

const context = {
  season: 2026,
  calendar: [{ round: 9, gpKey: "Great Britain", circuit: "Silverstone" }],
} as Pick<SeasonData, "season" | "calendar">;
const candidate = {
  round: 9,
  gpKey: "Great Britain",
  circuit: "Silverstone",
  name: "British Grand Prix",
  circuitInfo: {
    laps: 52,
    geometry: { viewBox: "0 0 100 100", path: "M 0 0 L 80 80 Z", corners: [] },
  },
};

describe("F1 legacy outline loader", () => {
  const originalFetch = global.fetch;
  afterEach(() => {
    global.fetch = originalFetch;
  });
  function respond(data = candidate) {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => data });
  }
  it("preserves unreviewed geometry, venue facts and the raw response", async () => {
    respond();
    const result = await fetchRoundData(9, "/data", context);
    expect(result.circuitInfo.geometry).toBe(candidate.circuitInfo.geometry);
    expect(result.circuitInfo.laps).toBe(52);
    expect(result.circuit).toBe("Silverstone");
    expect(candidate.circuitInfo.geometry.path).toBeTruthy();
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
  it("keeps legacy presentation when the calendar is unavailable", async () => {
    respond();
    expect((await fetchRoundData(9)).circuitInfo.geometry).toBe(candidate.circuitInfo.geometry);
  });
  it("rejects a response with a different requested round", async () => {
    respond({ ...candidate, round: 8 });
    await expect(fetchRoundData(9, "/data", context)).rejects.toThrow("different round identity");
  });
  it("does not borrow an outline from another venue", async () => {
    respond({ ...candidate, gpKey: "Austria", circuit: "Red Bull Ring" });
    expect((await fetchRoundData(9, "/data", context)).circuitInfo.geometry).toBeNull();
  });
  it("preserves the actual Monaco outline and provider metadata with no new fetch", async () => {
    const raw = JSON.parse(readFileSync(resolve("public/data/rounds/round_06.json"), "utf8"));
    respond(raw);
    const season = JSON.parse(readFileSync(resolve("public/data/season.json"), "utf8"));
    const result = await fetchRoundData(6, "/data", season);
    expect(result.circuitInfo.geometry).toBe(raw.circuitInfo.geometry);
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
  it("retains the actual Hungaroring outline without duplicating ambiguous corner labels", async () => {
    const raw = JSON.parse(readFileSync(resolve("public/data/rounds/round_11.json"), "utf8"));
    respond(raw);
    const result = await fetchRoundData(11);
    expect(result.circuitInfo.geometry?.path).toBe(raw.circuitInfo.geometry.path);
    expect(result.circuitInfo.geometry?.corners).toHaveLength(12);
    expect(raw.circuitInfo.geometry.corners).toHaveLength(16);
  });
  it("quarantines the actual conflicting path even if season context is unavailable", async () => {
    const raw = JSON.parse(readFileSync(resolve("public/data/rounds/round_08.json"), "utf8"));
    respond(raw);
    expect((await fetchRoundData(8)).circuitInfo.geometry).toBeNull();
    expect(raw.circuitInfo.geometry.path).toBeTruthy();
  });
});
