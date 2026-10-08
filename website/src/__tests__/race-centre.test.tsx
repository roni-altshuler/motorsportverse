import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { RaceCentre } from '@/components/landing/RaceCentre';
import type { RaceFeed } from '@/lib/race-centre';
const feed: RaceFeed = { asOf: '2099-01-01', series: [{ slug: 'f1-predictions', sport: 'Formula 1', accent: '#ff5555', href: '/f1/', rounds: 5, verdict: 'inconclusive', baseline: 'Grid', modelError: 3, baselineError: 2.9, note: 'No demonstrated edge.' }], events: [{
  id: 'f1-1', slug: 'f1-predictions', sport: 'Formula 1', accent: '#ff5555', round: 1, season: 2099, name: 'Test Grand Prix', location: 'Test circuit', date: '2099-02-01', completed: false, updatedAt: '2099-01-01T00:00:00Z', href: '/f1/', session: 'Race', calibrated: false,
  contenders: [{ code: 'AAA', name: 'Real Driver', team: 'Team A', win: .5, podium: .8 }],
}] };
beforeEach(() => { localStorage.clear(); window.history.replaceState({}, '', '/'); });
it('searches, switches forecast markets and shows measured evidence', () => {
  render(<RaceCentre feed={feed} />); expect(screen.getAllByText('50.0%').length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole('button', { name: 'Podium' }));
  expect(screen.getByText('80.0%')).toBeInTheDocument(); expect(screen.getByText('No clear edge yet')).toBeInTheDocument();
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'no match' } });
  expect(screen.getByText('No races in this view.')).toBeInTheDocument();
});
it('restores followed series after remount', () => {
  const first = render(<RaceCentre feed={feed} />);
  fireEvent.click(screen.getByRole('button', { name: 'Follow Formula 1' }));
  expect(JSON.parse(localStorage.getItem('motorsportverse:favourite-series:v1')!)).toEqual(['f1-predictions']); first.unmount();
  render(<RaceCentre feed={feed} />);
  expect(screen.getByRole('button', { name: 'Unfollow Formula 1' })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(screen.getByRole('button', { name: '★ Following' }));
  expect(screen.getByRole('link', { name: /Explore Formula 1/ })).toHaveAttribute('href', '/f1/');
});
it('does not show expired forecasts as future predictions', () => {
  render(<RaceCentre feed={{ ...feed, events: [{ ...feed.events[0], date: '2000-01-01' }] }} />);
  fireEvent.click(screen.getByRole('button', { name: 'Full calendar' }));
  expect(screen.getByText('Waiting for the result.')).toBeInTheDocument(); expect(screen.queryByText('50.0%')).not.toBeInTheDocument();
});

it('opens a linked race even when it is outside the default upcoming view', () => {
  window.history.replaceState({}, '', '/?race=finished#race-centre');
  render(<RaceCentre feed={{ ...feed, events: [...feed.events, { ...feed.events[0], id: 'finished', name: 'Past Grand Prix', date: '2000-01-01', completed: true }] }} />);
  expect(screen.getByRole('heading', { name: 'Past Grand Prix' })).toBeInTheDocument();
  expect(screen.getByText('The result is in.')).toBeInTheDocument();
});

it('filters to available forecasts and clears that restriction for results', () => {
  render(<RaceCentre feed={{ ...feed, events: [...feed.events, { ...feed.events[0], id: 'missing', name: 'Missing forecast', contenders: [] }, { ...feed.events[0], id: 'done', name: 'Finished race', completed: true }] }} />);
  fireEvent.click(screen.getByRole('checkbox', { name: 'Forecasts ready' }));
  expect(screen.queryByText('Missing forecast')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Results' }));
  expect(screen.getByRole('heading', { name: 'Finished race' })).toBeInTheDocument();
  expect(screen.getByRole('checkbox', { name: 'Forecasts ready' })).not.toBeChecked();
});

it('copies a shareable link to the selected race', async () => {
  const writeText = jest.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
  render(<RaceCentre feed={feed} />);
  fireEvent.click(screen.getByRole('button', { name: /Copy race link/ }));
  await waitFor(() => expect(screen.getByText('Race link copied.')).toBeInTheDocument());
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining('?race=f1-1#race-centre'));
});

it('keeps a linked historical race visible without expanding the whole season', () => {
  const events = Array.from({ length: 20 }, (_, i) => ({ ...feed.events[0], id: `past-${i}`, name: `Race ${i}`, date: `2000-01-${String(i + 1).padStart(2, '0')}`, completed: true }));
  window.history.replaceState({}, '', '/?race=past-0#race-centre');
  render(<RaceCentre feed={{ ...feed, events }} />);
  expect(screen.getByRole('button', { name: /Race 0 .*Results recorded/ })).toHaveAttribute('aria-pressed', 'true');
  expect(document.querySelectorAll('.race-row')).toHaveLength(9);
  expect(screen.getByRole('button', { name: 'Results' })).toHaveAttribute('aria-pressed', 'true');
});

it('uses the browser UTC day immediately and retires forecasts across midnight', () => {
  jest.useFakeTimers();
  jest.setSystemTime(new Date('2099-01-31T23:59:30Z'));
  try {
    render(<RaceCentre feed={{ ...feed, asOf: '2000-01-01', events: [{ ...feed.events[0], date: '2099-01-31' }] }} />);
    expect(screen.getAllByText('50.0%').length).toBeGreaterThan(0);
    act(() => { jest.advanceTimersByTime(60000); });
    expect(screen.queryByText('50.0%')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Full calendar' }));
    expect(screen.getByText('Waiting for the result.')).toBeInTheDocument();
  } finally { jest.useRealTimers(); }
});

it('opens history links after filtering and resets forecast-only and search filters', () => {
  const historical = { ...feed.events[0], id: 'done', name: 'Historical race', date: '2000-01-01', completed: true };
  render(<RaceCentre feed={{ ...feed, events: [...feed.events, historical] }} />);
  fireEvent.click(screen.getByRole('checkbox', { name: 'Forecasts ready' }));
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'no match' } });
  window.history.pushState({}, '', '/?race=done#race-centre');
  fireEvent(window, new PopStateEvent('popstate'));
  expect(screen.getByRole('heading', { name: 'Historical race' })).toBeInTheDocument();
  expect(screen.getByRole('searchbox')).toHaveValue('');
  expect(screen.getByRole('checkbox', { name: 'Forecasts ready' })).not.toBeChecked();
});

it('ignores corrupt or unknown favourites and still follows in privacy mode', () => {
  localStorage.setItem('motorsportverse:favourite-series:v1', '{invalid json');
  const first = render(<RaceCentre feed={feed} />);
  expect(screen.getByRole('button', { name: 'Follow Formula 1' })).toBeInTheDocument();
  first.unmount();
  localStorage.setItem('motorsportverse:favourite-series:v1', JSON.stringify(['unknown-series', 42]));
  const read = jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Storage blocked'); });
  const write = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Storage blocked'); });
  try {
    render(<RaceCentre feed={feed} />);
    fireEvent.click(screen.getByRole('button', { name: 'Follow Formula 1' }));
    expect(screen.getByRole('button', { name: 'Unfollow Formula 1' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: '★ Following' }));
    expect(screen.getByRole('heading', { name: 'Test Grand Prix' })).toBeInTheDocument();
  } finally { read.mockRestore(); write.mockRestore(); }
});
