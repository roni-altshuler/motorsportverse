import { act, render, screen } from '@testing-library/react';
import { RaceDetail } from '@/components/race-detail/RaceDetail';
import { fetchF2Data, fetchRoundDetail, fetchRoundProbabilities } from '@/lib/f2client';
import { useSeason } from '@/lib/SeasonProvider';
import type { RoundDetail } from '@/types/f2';
import published from '../../public/data/rounds/round_01.json';

jest.mock('@/lib/SeasonProvider', () => ({ useSeason: jest.fn() }));
jest.mock('@/lib/f2client', () => ({ fetchF2Data: jest.fn(), fetchRoundDetail: jest.fn(), fetchRoundProbabilities: jest.fn() }));
jest.mock('@/lib/useReducedMotion', () => ({ useReducedMotion: () => true }));

const baked = published as RoundDetail;
const season = jest.mocked(useSeason);
const detail = jest.mocked(fetchRoundDetail);
function select(year: number) {
  season.mockReturnValue({ year, basePath: year === 2026 ? '' : `/data/seasons/${year}`, index: { current: 2026, available: [2026, 2025, 2024], archived: [2025, 2024], lastUpdated: '', seasons: [] }, hasMultiple: true, setYear: jest.fn() });
}
beforeEach(() => {
  jest.clearAllMocks();
  select(2026);
  jest.mocked(fetchRoundProbabilities).mockResolvedValue(null);
  jest.mocked(fetchF2Data).mockResolvedValue(null);
});

it('restores baked current data immediately and does not leak a loaded archive into another year', async () => {
  const archive = { ...baked, season: 2025, venueName: 'Archive fixture venue' };
  detail.mockResolvedValue(archive);
  const page = render(<RaceDetail round={baked} probabilities={null} />);
  expect(screen.getByRole('heading', { name: baked.venueName })).toBeInTheDocument();
  expect(detail).not.toHaveBeenCalled();
  select(2025);
  await act(async () => { page.rerender(<RaceDetail round={baked} probabilities={null} />); });
  expect(screen.getByRole('heading', { name: archive.venueName })).toBeInTheDocument();
  select(2026);
  page.rerender(<RaceDetail round={baked} probabilities={null} />);
  expect(screen.getByRole('heading', { name: baked.venueName })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: archive.venueName })).not.toBeInTheDocument();
  detail.mockReturnValue(new Promise(() => {}));
  select(2024);
  page.rerender(<RaceDetail round={baked} probabilities={null} />);
  expect(screen.queryByRole('heading', { name: archive.venueName })).not.toBeInTheDocument();
});

it('ignores a late archive response after returning to the current season', async () => {
  let resolveArchive!: (value: RoundDetail) => void;
  detail.mockReturnValue(new Promise(resolve => { resolveArchive = resolve; }));
  select(2025);
  const page = render(<RaceDetail round={baked} probabilities={null} />);
  select(2026);
  page.rerender(<RaceDetail round={baked} probabilities={null} />);
  await act(async () => { resolveArchive({ ...baked, venueName: 'Late archive fixture' }); });
  expect(screen.getByRole('heading', { name: baked.venueName })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Late archive fixture' })).not.toBeInTheDocument();
});

it('does not show an archive from the previous round while the next round loads', async () => {
  select(2025);
  detail.mockResolvedValue({ ...baked, venueName: 'Round one archive fixture' });
  const page = render(<RaceDetail round={baked} probabilities={null} />);
  await act(async () => {});
  expect(screen.getByRole('heading', { name: 'Round one archive fixture' })).toBeInTheDocument();
  detail.mockReturnValue(new Promise(() => {}));
  page.rerender(<RaceDetail round={{ ...baked, round: 2, venueName: 'Round two fixture' }} probabilities={null} />);
  expect(screen.getByRole('heading', { name: 'Round two fixture' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'Round one archive fixture' })).not.toBeInTheDocument();
});
