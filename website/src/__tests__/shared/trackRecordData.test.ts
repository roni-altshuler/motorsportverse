import { createHash } from "node:crypto";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadTrackRecord } from "@/lib/trackRecordData";

let root: string;
const event = { round: 1, name: "Test GP", gpKey: "Test", circuit: "Test circuit", date: "2026-01-10", raceStartUtc: "2026-01-10T14:00:00Z" };
const forecast = { ...event, generatedAt: "2026-01-09T10:00:00Z", classification: [{ driver: "A", position: 1 }, { driver: "B", position: 2 }] };
const result = { ...forecast, classification: [{ driver: "B", position: 1 }, { driver: "A", position: 2 }], actualResults: { A: 1, B: 2 }, weekendResults: { sessions: [{ key: "grandPrix", kind: "race", status: "official" }] } };
const commit = "1".repeat(40);
function put(file: string, value: unknown) { mkdirSync(join(root, file, ".."), { recursive: true }); writeFileSync(join(root, file), JSON.stringify(value)); }
function receipt(artifact = forecast) {
  put("forecasts/original.json", artifact);
  return { season: 2026, round: 1, scope: "race", forecastKind: "model_forecast", artifactFile: "forecasts/original.json",
    artifactSha256: createHash("sha256").update(readFileSync(join(root, "forecasts/original.json"))).digest("hex"),
    sealedAt: "2026-01-09T11:00:00Z", sourceCommit: commit,
    verification: { kind: "audited_publication_event", publishedAt: "2026-01-09T12:00:00Z", eventUrl: "https://github.com/roni-altshuler/motorsportverse/actions/runs/123456789",
      artifactUrl: `https://raw.githubusercontent.com/roni-altshuler/motorsportverse/${commit}/projects/f1-predictions/website/public/data/forecasts/original.json` } };
}
function load() { return loadTrackRecord("f1", root, "2026-02-01").records[0]; }
beforeEach(() => { root = mkdtempSync(join(tmpdir(), "winner-record-test-")); put("season.json", { season: 2026, calendar: [event] }); put("rounds/round_01.json", result); });
afterEach(() => rmSync(root, { recursive: true, force: true }));

it("does not turn saved snapshot timestamps or replay grades into prospective accuracy", () => {
  put("forward_eval/season.json", { winnerHitRate: 1, basis: "walk_forward_replay" });
  expect(load()).toMatchObject({ status: "unverified", correct: null, predictedWinner: "B", actualWinner: "A" });
});
it("uses the unique original immutable pick, not an overwritten snapshot or intersection", () => {
  put("forecast_receipts.json", { schemaVersion: 1, forecasts: [receipt()] });
  expect(load()).toMatchObject({ status: "scored", correct: true, predictedWinner: "A", actualWinner: "A", forecastSource: "forecasts/original.json", publication: "2026-01-09T12:00:00Z" });
});
it.each(["hash", "baseline", "duplicate", "late", "nozone", "path", "noaudit", "contradiction", "held_original", "replay"])("rejects invalid publication evidence: %s", kind => {
  const original = { ...forecast, ...(kind === "contradiction" ? { generatedAt: "2026-01-11T00:00:00Z" } : {}), ...(kind === "held_original" ? { publicationHold: {} } : {}), ...(kind === "replay" ? { basis: "walk_forward_replay" } : {}) };
  const r = receipt(original);
  if (kind === "hash") r.artifactSha256 = "bad";
  if (kind === "baseline") r.forecastKind = "official_grid_baseline";
  if (kind === "late") r.verification.publishedAt = "2026-01-10T15:00:00Z";
  if (kind === "nozone") r.sealedAt = "2026-01-09T11:00:00";
  if (kind === "path") r.artifactFile = "../outside.json";
  if (kind === "noaudit") r.verification.kind = "self_declared_timestamp";
  put("forecast_receipts.json", { schemaVersion: 1, forecasts: kind === "duplicate" ? [r, r] : [r] });
  expect(load().status).not.toBe("scored");
});
it.each(["held", "unofficial", "synthetic", "missing_p1", "duplicate_p1", "wrong_event"])("does not grade an ineligible result: %s", kind => {
  put("forecast_receipts.json", { schemaVersion: 1, forecasts: [receipt()] });
  const r = { ...result, ...(kind === "held" ? { publicationHold: {} } : {}), ...(kind === "unofficial" ? { weekendResults: { sessions: [] } } : {}), ...(kind === "synthetic" ? { dataSource: "synthetic" } : {}), ...(kind === "missing_p1" ? { actualResults: { A: 2, B: 3 } } : {}), ...(kind === "duplicate_p1" ? { actualResults: { A: 1, B: 1 } } : {}), ...(kind === "wrong_event" ? { gpKey: "Wrong" } : {}) };
  put("rounds/round_01.json", r);
  expect(load().status).not.toBe("scored");
  expect(load().correct).toBeNull();
});
it("keeps missing calendar events and unknown dates inspectable without invented timing", () => {
  put("season.json", { season: 2026, calendar: [{ ...event, date: undefined }, { ...event, round: 2 }] });
  expect(loadTrackRecord("f1", root, "2026-02-01").records.map(r => r.status)).toEqual(["incomplete", "missing"]);
});
it("does not relabel an incorrectly copied archive as a different season", () => {
  put("seasons/2025/season.json", { season: 2026, calendar: [event] }); put("seasons/2025/rounds/round_01.json", result);
  const rows = loadTrackRecord("f1", root, "2026-02-01").records.filter(r => r.season === 2025);
  expect(rows).toHaveLength(1); expect(rows[0].status).toBe("incomplete");
});
it("does not use the main-race date as an unknown sprint date", () => {
  put("motogp.json", { season: 2026, calendar: [{ round: 1, key: "test", name: "Test", date: "2026-01-10", completed: true }] });
  put("rounds/round_01.json", { round: 1, season: 2026, venueKey: "test", completed: true, feature: { classification: [{ code: "A", position: 1 }], actualResults: [{ code: "A", position: 1 }] }, sprint: { classification: [{ code: "A", position: 1 }], actualResults: [{ code: "A", position: 1 }] } });
  expect(loadTrackRecord("motogp", root, "2026-02-01").records.find(r => r.scope === "sprint")).toMatchObject({ date: null, status: "incomplete" });
});
it("limits an event-only class to recorded participation and retains missing season-class coverage", () => {
  put("wec.json", { season: 2026, classes: [{ key: "HYPERCAR" }], calendar: [{ round: 1, name: "Test", completed: true }, { round: 2, name: "Missing" }] });
  put("rounds/round_01.json", { round: 1, season: 2026, event: "Test", classes: [{ key: "HYPERCAR" }, { key: "LMP2" }] });
  const rows = loadTrackRecord("wec", root, "2026-02-01").records;
  expect(rows.filter(r => r.scope === "LMP2").map(r => r.round)).toEqual([1]);
  expect(rows.find(r => r.scope === "HYPERCAR" && r.round === 2)?.status).toBe("missing");
});

it.each(["settled", "incomplete", "incomplete_stage", "synthetic", "held_original"])("checks scoped completion, holds and identity: %s", kind => {
  const stage = { classification: [{ code: "A", position: 1 }], actualResults: [{ code: "A", position: 1 }], ...(kind === "incomplete_stage" ? { completed: false } : {}) };
  put("f2.json", { season: 2026, calendar: [{ round: 1, key: "test", name: "Test", featureDate: "2026-01-10", sprintDate: "2026-01-09", completed: true }] });
  put("rounds/round_01.json", { round: 1, season: 2026, venueKey: "test", completed: kind !== "incomplete", dataSource: kind === "synthetic" ? "synthetic" : "snapshot", feature: stage });
  const original = { round: 1, season: 2026, venueKey: "test", completed: false, feature: { classification: stage.classification, ...(kind === "held_original" ? { publicationHold: {} } : {}) } };
  put("forecasts/original.json", original);
  const r = receipt();
  put("forecasts/original.json", original);
  r.scope = "feature";
  r.artifactSha256 = createHash("sha256").update(readFileSync(join(root, r.artifactFile))).digest("hex");
  r.verification.artifactUrl = r.verification.artifactUrl.replace("f1-predictions", "f2-predictions");
  put("forecast_receipts.json", { schemaVersion: 1, forecasts: [r] });
  const row = loadTrackRecord("f2", root, "2026-02-01").records.find(row => row.scope === "feature");
  expect(row?.status === "scored").toBe(kind === "settled");
});
it("does not pick the first of duplicate class records", () => {
  const stage = { classification: [{ code: "A", position: 1 }], actualResults: [{ code: "A", position: 1 }] };
  put("wec.json", { season: 2026, classes: [{ key: "HYPERCAR" }], calendar: [{ round: 1, name: "Test", date: "2026-01-10", completed: true }] });
  put("rounds/round_01.json", { round: 1, season: 2026, event: "Test", completed: true, classes: [{ key: "HYPERCAR", ...stage }, { key: "HYPERCAR", ...stage }] });
  expect(loadTrackRecord("wec", root, "2026-02-01").records[0].status).toBe("incomplete");
});
it("does not grade a known future start on the same calendar day", () => {
  put("forecast_receipts.json", { schemaVersion: 1, forecasts: [receipt()] });
  expect(loadTrackRecord("f1", root, "2026-01-10T12:00:00Z").records[0].status).toBe("pending");
  expect(loadTrackRecord("f1", root, "2026-01-11T12:00:00Z").records[0].status).toBe("scored");
});
