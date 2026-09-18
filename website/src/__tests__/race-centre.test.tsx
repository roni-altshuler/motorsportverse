import { fireEvent, render, screen } from '@testing-library/react';
import { RaceCentre } from '@/components/landing/RaceCentre';
import type { RaceFeed } from '@/lib/race-centre';
const feed: RaceFeed = { asOf: '2099-01-01', series: [{ slug: 'f1-predictions', sport: 'Formula 1', accent: '#ff5555', href: '/f1/', rounds: 5, verdict: 'inconclusive', baseline: 'Grid', modelError: 3, baselineError: 2.9, note: 'No demonstrated edge.' }], events: [{
  id: 'f1-1', slug: 'f1-predictions', sport: 'Formula 1', accent: '#ff5555', round: 1, season: 2099, name: 'Test Grand Prix', location: 'Test circuit', date: '2099-02-01', completed: false, updatedAt: '2099-01-01T00:00:00Z', href: '/f1/', session: 'Race', calibrated: false,
  contenders: [{ code: 'AAA', name: 'Real Driver', team: 'Team A', win: .5, podium: .8 }],
}] };
beforeEach(() => localStorage.clear());
it('searches, switches forecast markets and shows measured evidence', () => {
  render(<RaceCentre feed={feed} />); expect(screen.getByText('50.0%')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Podium', exact: true }));
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
