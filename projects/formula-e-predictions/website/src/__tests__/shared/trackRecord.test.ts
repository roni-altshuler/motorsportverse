import { calendarDate, summarize, uniqueWinner, winnerTimeline, winnerWeeks, type WinnerRecord } from "@/lib/trackRecord";

export function record(id: number, date: string | null, correct = true, extra: Partial<WinnerRecord> = {}): WinnerRecord {
  return { id: `test:2026:${id}:race`, season: 2026, round: id, scope: "race", scopeLabel: "Race", event: `Test race ${id}`,
    date, predictedWinner: "A", actualWinner: correct ? "A" : "B", correct, status: "scored", reason: "Explicit test record",
    modelVersion: null, source: "test fixture", publication: "2026-01-01T00:00:00Z", forecastSource: null,
    forecastSha256: null, sourceCommit: null, publicationEvent: null, positions: [], ...extra };
}

describe("winner record counts", () => {
  it("has no percentage before eligible settled races exist", () => {
    expect(summarize([], 2026, "race")).toEqual({ correct: 0, settled: 0, accuracy: null });
    expect(winnerTimeline([record(1, null), record(2, "2026-02-30")], 2026, "race")).toEqual([]);
    expect(calendarDate("20260101")).toBeNull();
  });
  it("requires unique original P1 rather than the minimum shared position", () => {
    expect(uniqueWinner([{ id: "B", name: "B", predicted: 2, actual: 2 }], "predicted")).toBeNull();
    expect(uniqueWinner([{ id: "A", name: "A", predicted: 1, actual: 2 }, { id: "B", name: "B", predicted: 1, actual: 1 }], "predicted")).toBeNull();
  });
  it("sorts dates and batches ties independently of input/round ordering", () => {
    const rows = [record(8, "2026-02-02", false), record(3, "2026-01-01"), record(1, "2026-02-02")];
    const points = winnerTimeline(rows, 2026, "race");
    expect(points.map(p => [p.date, p.correct, p.settled])).toEqual([["2026-01-01", 1, 1], ["2026-02-02", 2, 3]]);
    expect(winnerTimeline(rows.slice().reverse(), 2026, "race")).toEqual(points);
    expect(points[1].accuracy).toBeLessThan(points[0].accuracy);
    expect(points[1].recentAccuracy).toBe(50);
    expect(summarize(rows, 2026, "race").accuracy).toBe(points.at(-1)?.accuracy);
  });
  it("uses 28 inclusive UTC dates with the real window denominator", () => {
    const points = winnerTimeline([record(1, "2026-01-01"), record(2, "2026-01-02", false), record(3, "2026-01-29")], 2026, "race");
    expect(points[2]).toMatchObject({ windowStart: "2026-01-02", windowEnd: "2026-01-29", recentCorrect: 1, recentSettled: 2, recentAccuracy: 50 });
  });
  it("pools unequal and partial calendar weeks by counts, not mean percentages", () => {
    const rows = [record(1, "2026-01-04"), record(2, "2026-01-05", false), record(3, "2026-01-06", false), record(4, "2026-01-07")];
    expect(winnerWeeks(rows, 2026, "race")).toEqual([{ week: "2025-12-29", correct: 1, settled: 1 }, { week: "2026-01-05", correct: 1, settled: 3 }]);
    expect(summarize(rows, 2026, "race").accuracy).toBe(50);
  });
  it("isolates season rollover, sprint/main and class identities", () => {
    const rows = [record(1, "2026-01-01"), record(2, "2025-12-31", false, { season: 2025 }), record(3, "2026-01-02", false, { scope: "sprint" }), record(4, "2026-01-02", false, { scope: "GTP" })];
    expect(summarize(rows, 2026, "race")).toEqual({ correct: 1, settled: 1, accuracy: 100 });
    expect(winnerTimeline(rows, 2025, "race")[0].settled).toBe(1);
  });
  it("excludes pending, held, unverified, incomplete and duplicate records", () => {
    const rows = [record(1, "2026-01-01"), record(1, "2026-01-01"), ...(["pending", "held", "missing", "unverified", "incomplete"] as const).map((status, i) => record(i + 2, "2026-01-02", true, { status, correct: null }))];
    expect(summarize(rows, 2026, "race").settled).toBe(0);
  });
  it("reconciles headline, every date and eligible ledger on a nonmonotonic season", () => {
    const rows = Array.from({ length: 40 }, (_, i) => record(i + 1, new Date(Date.UTC(2026, 0, 1 + i)).toISOString().slice(0, 10), i % 3 === 0));
    const points = winnerTimeline(rows, 2026, "race");
    for (const point of points) {
      const eligible = rows.filter(r => (r.date as string) <= point.date);
      expect(point.settled).toBe(eligible.length);
      expect(point.correct).toBe(eligible.filter(r => r.correct).length);
    }
    expect(points.at(-1)).toMatchObject(summarize(rows, 2026, "race"));
    expect(points.some((p, i) => i > 0 && p.accuracy < points[i - 1].accuracy)).toBe(true);
  });
});
