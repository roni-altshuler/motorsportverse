import { fireEvent, render, screen, within } from '@testing-library/react';
import { ForecastExplorer } from '@/components/landing/ForecastExplorer';
import type { RaceEvent } from '@/lib/race-centre';
const event = {
  session: 'Race', calibrated: false, accent: '#ff5555',
  contenders: [40, 20, 15, 10, 8, 7].map((p, i) => ({ code: `D${i}`, name: `Driver ${i}`, team: `Team ${i}`, win: p / 100, podium: .5 })),
} as RaceEvent;
it('expands the full field and compares two drivers with percentage-point differences', () => {
  render(<ForecastExplorer event={event} />);
  expect(screen.queryByText('Driver 5')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Explore all 6 drivers' }));
  expect(screen.getByText('Driver 5')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Compare drivers' }));
  const comparison = screen.getByRole('region', { name: 'Driver comparison' });
  expect(within(comparison).getByText('20.0 percentage-point')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Second driver'), { target: { value: 'D5' } });
  expect(within(comparison).getByText('33.0 percentage-point')).toBeInTheDocument();
  expect(within(screen.getByLabelText('First driver')).queryByRole('option', { name: 'Driver 5' })).not.toBeInTheDocument();
});
it('leaves unavailable podium probabilities unavailable', () => {
  render(<ForecastExplorer event={{ ...event, contenders: event.contenders.map(d => ({ ...d, podium: null })) }} />);
  expect(screen.getByRole('button', { name: 'Podium', exact: true })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Compare drivers' }));
  expect(within(screen.getByRole('table')).getAllByText('—')).toHaveLength(2);
});
