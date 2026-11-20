import { render, screen } from '@testing-library/react';
import StandingsPage, { type StandingsPageProps } from '@/components/StandingsPage';

let mockQuery = '';

jest.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(mockQuery),
}));
jest.mock('@/lib/f2client', () => ({
  useSeasonF2Data: () => ({ data: null, isArchived: false }),
}));
// KPI presentation (and its ESM icon bundle) is outside this routing unit test.
// The production browser campaign renders the real component.
jest.mock('@/components/standings/ChampionshipKPIs', () => ({
  __esModule: true, default: () => null,
}));
jest.mock('next/link', () => {
  // Load the real framework Link with the same base path as the Pages export.
  // Its addBasePath module captures this setting when it is first imported.
  const previous = process.env.__NEXT_ROUTER_BASEPATH;
  process.env.__NEXT_ROUTER_BASEPATH = '/motorsportverse/projects/f2';
  try {
    return jest.requireActual('next/link');
  } finally {
    if (previous === undefined) delete process.env.__NEXT_ROUTER_BASEPATH;
    else process.env.__NEXT_ROUTER_BASEPATH = previous;
  }
});

const props: StandingsPageProps = {
  season: 2026, completedRounds: 0, totalRounds: 14, lastUpdatedRound: 0,
  drivers: [], teams: [], championship: [], rounds: [],
  driverSeries: [], teamSeries: [],
};
const tabs = [
  ['Drivers', 'drivers'],
  ['Teams', 'teams'],
  ['Who Can Still Win?', 'wdc'],
] as const;

beforeEach(() => { mockQuery = ''; });

it('keeps every query-tab destination inside the deployed F2 base path', () => {
  render(<StandingsPage {...props} />);
  for (const [name, tab] of tabs) {
    const link = screen.getByRole('link', { name });
    const url = new URL(link.getAttribute('href')!, 'https://example.test');
    expect(url.pathname.replace(/\/$/, '')).toBe('/motorsportverse/projects/f2/standings');
    expect(url.searchParams.get('tab')).toBe(tab);
    expect(url.hash).toBe('');
  }
});

it.each([
  ['', 'drivers'],
  ['tab=drivers', 'drivers'],
  ['tab=teams', 'teams'],
  ['tab=wdc', 'wdc'],
  ['tab=constructors', 'teams'],
  ['tab=whocanwin', 'wdc'],
  ['tab=unknown', 'drivers'],
])('selects the direct-entry query %s without changing its tab semantics', (query, selected) => {
  mockQuery = query;
  render(<StandingsPage {...props} />);
  for (const [name, tab] of tabs) {
    const link = screen.getByRole('link', { name });
    if (tab === selected) expect(link).toHaveClass('active');
    else expect(link).not.toHaveClass('active');
  }
  if (selected === 'drivers') expect(screen.getByRole('table', { name: 'Driver championship standings' })).toBeInTheDocument();
  if (selected === 'teams') expect(screen.getByRole('table', { name: 'Team championship standings' })).toBeInTheDocument();
  if (selected === 'wdc') expect(screen.getByRole('heading', { name: 'Teams Title Race' })).toBeInTheDocument();
});
