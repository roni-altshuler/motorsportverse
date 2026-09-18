/** Build-time adapter. Every number comes from committed series exports. */
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { Project } from '@/types/registry';
import type { RaceContender, RaceEvent, RaceFeed, SeriesEvidence } from './race-centre';

type RecordValue = Record<string, unknown>;
function obj(value: unknown): RecordValue {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : {};
}
function rows(value: unknown): RecordValue[] { return Array.isArray(value) ? value.map(obj) : []; }
function str(value: unknown): string | null { return typeof value === 'string' && value.trim() ? value : null; }
function number(value: unknown): number | null { return typeof value === 'number' && Number.isFinite(value) ? value : null; }
function read(path: string): RecordValue {
  if (!existsSync(path)) return {};
  // Malformed published data should fail the build, not silently become a forecast.
  return obj(JSON.parse(readFileSync(path, 'utf8')));
}
function dateOnly(value: unknown): string | null {
  const valueString = str(value)?.slice(0, 10);
  if (!valueString || !/^\d{4}-\d{2}-\d{2}$/.test(valueString)) return null;
  const stamp = Date.parse(`${valueString}T00:00:00Z`);
  return Number.isFinite(stamp) && new Date(stamp).toISOString().slice(0, 10) === valueString ? valueString : null;
}
function market(value: unknown): Map<string, number> {
  const entries = Array.isArray(value)
    ? rows(value).map(row => [str(row.driver), row.probability] as const)
    : Object.entries(obj(value)).map(([code, row]) => [code, obj(row).probability] as const);
  const out = new Map<string, number>();
  for (const [code, value] of entries) {
    const p = number(value);
    if (!code || p === null || p < 0 || p > 1 || out.has(code)) return new Map();
    out.set(code, p);
  }
  return out;
}
export function extractContenders(raw: RecordValue, roster: RecordValue[]): { contenders: RaceContender[]; session: string } {
  // Keep race types/class markets separate: a class win is not an overall win.
  const session = raw.feature ? 'Feature race' : raw.race ? 'Race' : raw.rally ? 'Rally' : 'Race';
  const payload = obj(raw.feature ?? raw.race ?? raw.rally ?? raw);
  const markets = obj(payload.markets);
  const wins = market(markets.win);
  const podium = market(markets.podium);
  if (!wins.size || Math.abs([...wins.values()].reduce((a, b) => a + b, 0) - 1) > 0.02) {
    return { contenders: [], session };
  }
  // A partial or contradictory podium column cannot support comparisons.
  const validPodium = podium.size === wins.size
    && [...wins].every(([code, win]) => (podium.get(code) ?? -1) + 1e-8 >= win)
    && Math.abs([...podium.values()].reduce((a, b) => a + b, 0) - Math.min(3, wins.size)) <= 0.02;
  const names = new Map(roster.map(row => [str(row.code), row]));
  const contenders = [...wins].sort((a, b) => b[1] - a[1]).map(([code, win]) => {
    const driver = names.get(code) ?? {};
    const p = validPodium ? podium.get(code) : undefined;
    return { code, name: str(driver.fullName) ?? str(driver.name) ?? code, team: str(driver.team) ?? '',
      win, podium: p !== undefined && p >= win ? p : null };
  });
  return { contenders, session };
}
const INDEX: Record<string, string> = { 'f1-predictions': 'season', 'formula-e-predictions': 'fe' };
export function getRaceFeed(projects: Project[], root = join(process.cwd(), '..'), now = new Date()): RaceFeed {
  const events: RaceEvent[] = [];
  const series: SeriesEvidence[] = [];
  for (const project of projects) {
    const dir = join(root, 'projects', project.slug, 'website', 'public', 'data');
    const index = read(join(dir, `${INDEX[project.slug] ?? project.slug.replace('-predictions', '')}.json`));
    const evidence = read(join(dir, 'evidence.json'));
    const headline = obj(evidence.headline);
    const href = project.website || `/projects/${project.slug}/`;
    series.push({ slug: project.slug, sport: project.sport, accent: project.accent || '#e7102f', href,
      rounds: number(headline.nRounds) ?? 0,
      verdict: str(headline.verdict) ?? 'unavailable', baseline: str(headline.baselineLabel),
      modelError: headline.metric === 'mean_position_error' ? number(headline.modelMean) : null,
      baselineError: headline.metric === 'mean_position_error' ? number(headline.baselineMean) : null,
      note: str(headline.note) ?? 'A scored model comparison is not available yet.' });
    const season = number(index.season);
    if (season === null) continue;
    const roster = rows(index.drivers ?? index.driverStandings);
    for (const race of rows(index.calendar)) {
      const round = number(race.round);
      if (round === null || race.postponed === true && !race.rescheduledDate) continue;
      const recorded = Array.isArray(index.completedRounds)
        ? index.completedRounds.includes(round)
        : round <= (number(index.completedRounds) ?? 0);
      const completed = typeof race.completed === 'boolean' ? race.completed : recorded;
      const raw = completed ? {} : read(join(dir, 'probabilities', `round_${String(round).padStart(2, '0')}.json`));
      // Never mix an old season's forecast into the current calendar.
      const valid = raw.season === season && raw.round === round;
      const extracted = valid ? extractContenders(raw, roster) : { contenders: [], session: 'Race' };
      events.push({ id: `${project.slug}-${season}-${round}`, slug: project.slug,
        sport: project.sport, accent: project.accent || '#e7102f', round, season,
        name: str(race.raceName) ?? str(race.event) ?? str(race.name) ?? `Round ${round}`,
        location: [str(race.circuit) ?? str(race.city) ?? str(race.place), str(race.country)].filter(Boolean).join(' · '),
        date: dateOnly(race.rescheduledDate ?? race.featureDate ?? race.raceDate ?? race.date), completed,
        updatedAt: str(raw.generatedAt) ?? str(index.generatedAt) ?? str(index.lastUpdated),
        href, ...extracted, calibrated: valid && obj(raw.calibration).applied === true });
    }
  }
  return { asOf: now.toISOString().slice(0, 10), events, series };
}
