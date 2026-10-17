/** Build-time, read-only adapter. Never imports forward-eval grades as forecasts. */
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { calendarDate, uniqueWinner, type RecordedPosition, type TrackRecordData, type WinnerRecord } from "./trackRecord";

type Json = Record<string, unknown>;
const obj = (value: unknown): Json => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Json : {};
const text = (value: unknown): string | null => typeof value === "string" && value.trim() ? value : null;
const list = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
const position = (value: unknown): number | null => typeof value === "number" && Number.isInteger(value) && value > 0 ? value : null;
function read(file: string): Json { try { return obj(JSON.parse(readFileSync(file, "utf8"))); } catch { return {}; } }
function timestamp(value: unknown): number | null {
  const s = text(value);
  if (!s || !/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(s) || !calendarDate(s.slice(0, 10))) return null;
  const n = Date.parse(s);
  return Number.isFinite(n) ? n : null;
}
const CONFIG: Record<string, { file: string; label: string; scopes: string[] }> = {
  f1: { file: "season.json", label: "Formula 1", scopes: ["race"] },
  f2: { file: "f2.json", label: "Formula 2", scopes: ["feature", "sprint"] },
  f3: { file: "f3.json", label: "Formula 3", scopes: ["feature", "sprint"] },
  "formula-e": { file: "fe.json", label: "Formula E", scopes: ["race"] },
  nascar: { file: "nascar.json", label: "NASCAR", scopes: ["race"] },
  indycar: { file: "indycar.json", label: "IndyCar", scopes: ["race"] },
  motogp: { file: "motogp.json", label: "MotoGP", scopes: ["feature", "sprint"] },
  wrc: { file: "wrc.json", label: "WRC", scopes: ["rally"] },
  wec: { file: "wec.json", label: "WEC", scopes: [] },
  imsa: { file: "imsa.json", label: "IMSA", scopes: [] },
};
function blocks(raw: Json, series: string): { scope: string; label: string; body: Json }[] {
  if (series === "f1") return [{ scope: "race", label: "Grand Prix", body: raw }];
  if (series === "wec" || series === "imsa") return list(raw.classes).flatMap(value => {
    const body = obj(value), scope = text(body.key);
    return scope ? [{ scope, label: text(body.label) ?? scope, body }] : [];
  });
  return CONFIG[series].scopes.map(scope => ({ scope, label: scope === "feature" ? "Main race" : scope === "sprint" ? "Sprint" : scope === "rally" ? "Rally" : "Race", body: obj(raw[scope]) }));
}
function positions(predicted: unknown, actual: unknown): { rows: RecordedPosition[]; valid: boolean } {
  const rows = new Map<string, RecordedPosition>();
  let valid = Array.isArray(predicted);
  for (const value of list(predicted)) {
    const row = obj(value), id = text(row.driver) ?? text(row.code), rank = position(row.position);
    if (!id || rank === null || rows.has(id)) { valid = false; continue; }
    const name = text(row.name) ?? text(row.driverFullName) ?? text(row.driverName) ?? (row.number && row.team ? `${row.team} #${row.number}` : id);
    rows.set(id, { id, name, predicted: rank, actual: null });
  }
  const actualRows = Array.isArray(actual) ? actual : Object.entries(obj(actual)).map(([id, value]) => ({ code: id, position: typeof value === "object" ? obj(value).position : value }));
  const seen = new Set<string>();
  for (const value of actualRows) {
    const row = obj(value), id = text(row.driver) ?? text(row.code), rank = position(row.position);
    if (!id || rank === null || seen.has(id)) { valid = false; continue; }
    seen.add(id);
    const item = rows.get(id) ?? { id, name: text(row.name) ?? id, predicted: null, actual: null };
    item.actual = rank;
    rows.set(id, item);
  }
  return { rows: [...rows.values()].sort((a, b) => (a.predicted ?? Infinity) - (b.predicted ?? Infinity) || a.id.localeCompare(b.id)), valid };
}
function identity(raw: Json, event: Json, season: number, series: string): boolean {
  if (raw.round !== event.round || (series !== "f1" && raw.season !== season)) return false;
  if (series === "f1") return ["name", "gpKey", "circuit", "date"].every(key => text(event[key]) !== null && raw[key] === event[key]);
  if (["date", "raceDate"].some(key => raw[key] != null && raw[key] !== event[key])) return false;
  if (series === "wec" || series === "imsa") return text(event.name) !== null && raw.event === event.name;
  return text(event.key) !== null && raw.venueKey === event.key;
}

/** Optional immutable model receipt contract, documented in docs/winner-track-record.md.
 * No receipts or forecasts are manufactured here. Baseline seals never qualify.
 */
function originalForecast(dir: string, receipts: unknown[], season: number, round: number, scope: string,
  series: string, event: Json, eventStart: number | null): { raw: Json; publication: string; file: string; hash: string; eventUrl: string; commit: string } | null {
  const matches = receipts.map(obj).filter(r => r.season === season && r.round === round && r.scope === scope);
  if (matches.length !== 1 || eventStart === null) return null;
  const receipt = matches[0], file = text(receipt.artifactFile), sealed = timestamp(receipt.sealedAt);
  const verification = obj(receipt.verification), published = timestamp(verification.publishedAt);
  const commit = text(receipt.sourceCommit), eventUrl = text(verification.eventUrl);
  // Publication evidence is a trusted, audited input, not inferred from a
  // generatedAt/sealedAt claim. This reader does not create or backfill it.
  if (receipt.forecastKind !== "model_forecast" || !file || !/^forecasts\/[A-Za-z0-9_.-]+\.json$/.test(file) ||
      sealed === null || sealed >= eventStart || typeof receipt.artifactSha256 !== "string" ||
      !commit || !/^[a-f0-9]{40}$/.test(commit) || verification.kind !== "audited_publication_event" ||
      published === null || published < sealed || published >= eventStart || !eventUrl ||
      !/^https:\/\/github\.com\/roni-altshuler\/motorsportverse\/actions\/runs\/\d+$/.test(eventUrl) ||
      verification.artifactUrl !== `https://raw.githubusercontent.com/roni-altshuler/motorsportverse/${commit}/projects/${series}-predictions/website/public/data/${file}`) return null;
  try {
    const bytes = readFileSync(join(dir, file));
    if (createHash("sha256").update(bytes).digest("hex") !== receipt.artifactSha256) return null;
    const raw = obj(JSON.parse(bytes.toString("utf8")));
    const scoped = blocks(raw, series).filter(b => b.scope === scope);
    if (scoped.length !== 1) return null;
    const body = scoped[0].body;
    const generated = timestamp(raw.generatedAt);
    if (!identity(raw, event, season, series) || raw.publicationHold != null || body.publicationHold != null || raw.completed === true ||
        (raw.generatedAt != null && (generated === null || generated > sealed)) ||
        body.completed === true || (body.generatedAt != null && (timestamp(body.generatedAt) === null || (timestamp(body.generatedAt) as number) > sealed)) ||
        (raw.forecastKind != null && raw.forecastKind !== "model_forecast") ||
        raw.dataSource === "synthetic" || body.dataSource === "synthetic" ||
        [raw.evaluationBasis, raw.basis, raw.evaluationStream, body.evaluationBasis, body.basis].some(v => typeof v === "string" && /replay|retrospective/i.test(v)) ||
        list(body.actualResults).length || Object.keys(obj(body.actualResults)).length) return null;
    return { raw, publication: String(verification.publishedAt), file, hash: receipt.artifactSha256, eventUrl, commit };
  } catch { return null; }
}

export function loadTrackRecord(series: string, dataRoot = join(process.cwd(), "public/data"),
  asOf = new Date().toISOString()): TrackRecordData {
  const config = CONFIG[series];
  if (!config) throw new Error(`Unknown series: ${series}`);
  const asOfDate = calendarDate(asOf.slice(0, 10));
  const asOfTime = timestamp(asOf) ?? (calendarDate(asOf) ? Date.parse(`${asOf}T00:00:00Z`) : null);
  if (!asOfDate || asOfTime === null) throw new Error("Invalid track-record review time");
  const current = read(join(dataRoot, config.file));
  const currentSeason = Number.isInteger(current.season) && Number(current.season) > 0 ? Number(current.season) : 0;
  const roots = [{ season: currentSeason, dir: dataRoot }];
  const archive = join(dataRoot, "seasons");
  if (existsSync(archive)) for (const year of readdirSync(archive)) {
    if (/^\d{4}$/.test(year) && Number(year) !== currentSeason) roots.push({ season: Number(year), dir: join(archive, year) });
  }
  const records: WinnerRecord[] = [];
  for (const { season, dir } of roots) {
    const main = read(join(dir, config.file)), calendar = list(main.calendar).map(obj);
    const roundsDir = join(dir, "rounds");
    const saved = new Map<number, string[]>();
    if (existsSync(roundsDir)) for (const file of readdirSync(roundsDir)) {
      const match = /^round_(\d+)\.json$/.exec(file);
      if (match) saved.set(Number(match[1]), [...(saved.get(Number(match[1])) ?? []), file]);
    }
    const receiptsFile = read(join(dir, "forecast_receipts.json"));
    const receipts = receiptsFile.schemaVersion === 1 ? list(receiptsFile.forecasts) : [];
    const roundNumbers = [...new Set([...calendar.map(e => e.round).filter((r): r is number => Number.isInteger(r) && Number(r) > 0), ...saved.keys()])].sort((a, b) => a - b);
    const allScopes = new Map<string, string>();
    for (const value of list(main.classes)) { const c = obj(value); if (text(c.key)) allScopes.set(String(c.key), text(c.label) ?? String(c.key)); }
    const seasonClasses = new Set(allScopes.keys());
    for (const files of saved.values()) for (const file of files) for (const block of blocks(read(join(roundsDir, file)), series)) allScopes.set(block.scope, block.label);
    if (!allScopes.size) for (const block of blocks({}, series)) allScopes.set(block.scope, block.label);
    for (const round of roundNumbers) {
      const events = calendar.filter(e => e.round === round), event = events[0] ?? {};
      const files = saved.get(round) ?? [], raw = files.length === 1 ? read(join(roundsDir, files[0])) : {};
      for (const [scope, scopeLabel] of allScopes) {
        if (series === "wec" || series === "imsa") {
          const entered = blocks(raw, series);
          // Extra classes (e.g. Le Mans LMP2) apply only where recorded. An
          // absent class on an otherwise recorded event is not a missing race.
          if (entered.length ? !entered.some(b => b.scope === scope) : !seasonClasses.has(scope)) continue;
        }
        const date = scope === "sprint" ? calendarDate(event.sprintDate) :
          calendarDate(event[scope === "feature" ? "featureDate" : "raceDate"]) ?? calendarDate(event.date);
        const start = (scope === "sprint" ? null : timestamp(event.raceStartUtc)) ?? (date ? Date.parse(`${date}T00:00:00Z`) : null);
        const original = originalForecast(dir, receipts, season, round, scope, series, event, start);
        const prediction = original?.raw ?? raw;
        const predScopes = blocks(prediction, series).filter(b => b.scope === scope);
        const resultScopes = blocks(raw, series).filter(b => b.scope === scope);
        const predBody = predScopes[0]?.body ?? {};
        const resultBody = resultScopes[0]?.body ?? {};
        const parsed = positions(predBody.classification, resultBody.actualResults);
        const predictedId = uniqueWinner(parsed.rows, "predicted"), actualId = uniqueWinner(parsed.rows, "actual");
        let status: WinnerRecord["status"] = "unverified", reason = "Original pre-race publication is not verified; excluded from accuracy.";
        const hasPrediction = parsed.rows.some(r => r.predicted !== null), hasActual = parsed.rows.some(r => r.actual !== null);
        const officialRace = list(obj(raw.weekendResults).sessions).map(obj).some(s => s.key === "grandPrix" && s.kind === "race" && s.status === "official");
        const settled = resultBody.completed !== false && (series === "f1" ? officialRace && raw.completed !== false && event.completed !== false : raw.completed === true && event.completed === true);
        if (raw.publicationHold != null || resultBody.publicationHold != null) { status = "held"; reason = "Forecast withheld from publication and scoring."; }
        else if (main.season !== season || season <= 0 || events.length !== 1 || files.length > 1 || !identity(raw, event, season, series)) { status = files.length ? "incomplete" : "missing"; reason = files.length ? "Season/event identity is missing or does not match the calendar." : series === "wec" || series === "imsa" ? "Class participation and forecast are not recorded for this event." : "No saved forecast for this calendar event."; }
        else if (predScopes.length > 1 || resultScopes.length > 1) { status = "incomplete"; reason = "Duplicate race or class records are ambiguous; no winner selected."; }
        else if (raw.dataSource === "synthetic" || resultBody.dataSource === "synthetic") { status = "unverified"; reason = "Synthetic results are excluded from the real-race track record."; }
        else if (!hasPrediction) { status = "missing"; reason = "No saved forecast for this race or class."; }
        else if (!date) { status = "incomplete"; reason = "Event date is not recorded; excluded from the dated track record."; }
        else if (!parsed.valid || !predictedId || (hasActual && !actualId)) { status = "incomplete"; reason = "An original P1 or complete position identity is missing or ambiguous; no winner inferred."; }
        else if (date > asOfDate || start !== null && start > asOfTime || !hasActual || !settled || [raw.status, event.status, resultBody.status].includes("provisional") || raw.provisional === true || resultBody.provisional === true) { status = "pending"; reason = original ? "Result settlement is not yet confirmed for this pre-race pick." : "Result settlement is not yet confirmed; original pre-race publication is also unverified."; }
        else if (original) { status = "scored"; reason = "Original pre-race model pick compared with the recorded race winner."; }
        else if (series === "f2" || timestamp(raw.generatedAt) !== null && start !== null && (timestamp(raw.generatedAt) as number) >= start) reason = "Historical comparison; this snapshot does not verify an original pre-race publication.";
        const model = obj(prediction.modelConfig);
        records.push({ id: `${series}:${season}:${round}:${scope}`, season, round, scope, scopeLabel,
          event: text(event.name) ?? text(raw.name) ?? text(raw.venueName) ?? `Round ${round}`, date,
          predictedWinner: predictedId, actualWinner: actualId, correct: status === "scored" ? predictedId === actualId : null,
          status, reason, modelVersion: text(prediction.modelVersion) ?? text(model.modelVersion),
          source: `${dir === dataRoot ? "" : `seasons/${season}/`}rounds/${files[0] ?? `round_${String(round).padStart(2, "0")}.json`}`,
          publication: original?.publication ?? null,
          forecastSource: original?.file ?? null, forecastSha256: original?.hash ?? null,
          publicationEvent: original?.eventUrl ?? null, sourceCommit: original?.commit ?? null,
          positions: parsed.rows });
      }
    }
  }
  return { series, label: config.label, currentSeason, asOf,
    evaluationBasis: text(read(join(dataRoot, "forward_eval/season.json")).basis), records };
}
