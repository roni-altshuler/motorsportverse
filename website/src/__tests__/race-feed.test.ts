import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { getRaceFeed, extractContenders } from '@/lib/race-feed';
import { isStale, raceStatus, type RaceEvent } from '@/lib/race-centre';
import type { Project } from '@/types/registry';
const project: Project = { slug: 'f2-predictions', name: 'F2', sport: 'Formula 2', maturity: 'production', category: 'open-wheel', summary: 'test' };
const forecast = { season: 2026, round: 3, feature: { markets: { win: { AAA: { probability: .7 }, BBB: { probability: .3 } } } } };
let root: string;
beforeEach(() => { root = mkdtempSync(join(tmpdir(), 'race-feed-')); });
afterEach(() => rmSync(root, { recursive: true, force: true }));
function publish(file: string, data: unknown) {
  const dir = join(root, 'projects/f2-predictions/website/public/data');
  mkdirSync(join(dir, 'probabilities'), { recursive: true }); writeFileSync(join(dir, file), JSON.stringify(data));
}
function index() {
  publish('f2.json', { season: 2026, generatedAt: '2026-09-01T12:00:00Z', calendar: [
    { round: 1, name: 'Scored', featureDate: '2026-08-01', completed: true },
    { round: 2, name: 'Missing result', featureDate: '2026-09-01', completed: false },
    { round: 3, name: 'Next race', featureDate: '2026-09-20', completed: false },
  ], driverStandings: [{ code: 'AAA', name: 'Real Driver' }] });
}
it('joins published forecasts by calendar round, season and roster', () => {
  index(); publish('probabilities/round_03.json', forecast);
  const feed = getRaceFeed([project], root, new Date('2026-09-18'));
  expect(feed.events.map(e => raceStatus(e, feed.asOf))).toEqual(['completed', 'awaiting', 'upcoming']);
  expect(feed.events[2].contenders[0]).toMatchObject({ name: 'Real Driver', win: .7 });
  expect(feed.events[0].contenders).toEqual([]); expect(isStale(feed.events[2], feed.asOf)).toBe(true);
});
it('rejects a forecast from another season or round', () => {
  index(); publish('probabilities/round_03.json', { ...forecast, season: 2025 });
  expect(getRaceFeed([project], root).events[2].contenders).toEqual([]);
  publish('probabilities/round_03.json', { ...forecast, round: 4 });
  expect(getRaceFeed([project], root).events[2].contenders).toEqual([]);
});
it('supports F1 arrays and rejects malformed probability mass', () => {
  const raw = { markets: { win: [{ driver: 'AAA', probability: .7 }, { driver: 'BBB', probability: .3 }] } };
  expect(extractContenders(raw, []).contenders).toHaveLength(2); raw.markets.win[1].probability = .7;
  expect(extractContenders(raw, []).contenders).toEqual([]);
});
it('never mistakes class win probabilities for an overall win market', () => {
  expect(extractContenders({ classes: [{ markets: { win: { AAA: { probability: 1 } } } }] }, []).contenders).toEqual([]);
});
it('handles unavailable evidence and missing dates honestly', () => {
  const feed = getRaceFeed([project], root); expect(feed.events).toEqual([]);
  expect(feed.series[0].verdict).toBe('unavailable');
  expect(raceStatus({ completed: false, date: null } as RaceEvent, '2026-09-18')).toBe('undated');
});
it('expires upcoming status as time passes', () => {
  const event = { completed: false, date: '2026-09-18' } as RaceEvent;
  expect(raceStatus(event, '2026-09-18')).toBe('upcoming'); expect(raceStatus(event, '2026-09-19')).toBe('awaiting');
});

it('uses explicit completed round IDs for the F1 calendar, including gaps', () => {
  publish('f2.json', { season: 2026, completedRounds: [1, 3], calendar: [
    { round: 1, date: '2026-03-01' }, { round: 2, date: '2026-03-08' }, { round: 3, date: '2026-03-15' },
  ] });
  expect(getRaceFeed([project], root).events.map(e => e.completed)).toEqual([true, false, true]);
});
