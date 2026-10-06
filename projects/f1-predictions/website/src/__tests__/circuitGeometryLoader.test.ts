import { fetchRoundData } from "@/lib/data";
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

describe("F1 map loader gate", () => {
  const originalFetch = global.fetch;
  afterEach(() => {
    global.fetch = originalFetch;
  });
  function respond(data = candidate) {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => data });
  }
  it("strips unverified geometry while preserving venue facts and the raw response", async () => {
    respond();
    const result = await fetchRoundData(9, "/data", context);
    expect(result.circuitInfo.geometry).toBeNull();
    expect(result.circuitInfo.laps).toBe(52);
    expect(result.circuit).toBe("Silverstone");
    expect(candidate.circuitInfo.geometry.path).toBeTruthy();
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
  it("does not guess an identity when the calendar is unavailable", async () => {
    respond();
    expect((await fetchRoundData(9)).circuitInfo.geometry).toBeNull();
  });
  it("rejects a response with a different requested round", async () => {
    respond({ ...candidate, round: 8 });
    await expect(fetchRoundData(9, "/data", context)).rejects.toThrow("different round identity");
  });
  it("does not borrow an outline from another venue", async () => {
    respond({ ...candidate, gpKey: "Austria", circuit: "Red Bull Ring" });
    expect((await fetchRoundData(9, "/data", context)).circuitInfo.geometry).toBeNull();
  });
});
