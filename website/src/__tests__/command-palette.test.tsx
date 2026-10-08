import { fireEvent, render, screen } from '@testing-library/react';
import { CommandPalette } from '@/components/CommandPalette';

const push = jest.fn();
jest.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));
const items = [
  { id: 'f1', label: 'Formula 1', group: 'Projects', href: '/f1/' },
  { id: 'f2', label: 'Formula 2', group: 'Projects', href: '/f2/' },
  { id: 'docs', label: 'Documentation', group: 'Learn', href: '/docs' },
];

beforeEach(() => {
  push.mockClear();
  HTMLElement.prototype.scrollIntoView = jest.fn();
});

it('resets keyboard selection when the search changes, then navigates the first match', () => {
  render(<CommandPalette items={items} />);
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  const search = screen.getByRole('textbox', { name: 'Search' });
  fireEvent.keyDown(search, { key: 'ArrowDown' });
  fireEvent.keyDown(search, { key: 'ArrowDown' });
  expect(screen.getByRole('option', { name: 'Documentation' })).toHaveAttribute('aria-selected', 'true');
  fireEvent.change(search, { target: { value: 'formula' } });
  expect(screen.getByRole('option', { name: 'Formula 1' })).toHaveAttribute('aria-selected', 'true');
  fireEvent.keyDown(search, { key: 'Enter' });
  expect(push).toHaveBeenCalledWith('/f1/');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

it('closes and reopens with a cleared search and selection', () => {
  render(<CommandPalette items={items} />);
  fireEvent(window, new Event('mv:open-palette'));
  fireEvent.change(screen.getByRole('textbox', { name: 'Search' }), { target: { value: 'docs' } });
  fireEvent.keyDown(screen.getByRole('textbox', { name: 'Search' }), { key: 'Escape' });
  fireEvent(window, new Event('mv:open-palette'));
  expect(screen.getByRole('textbox', { name: 'Search' })).toHaveValue('');
  expect(screen.getByRole('option', { name: 'Formula 1' })).toHaveAttribute('aria-selected', 'true');
});
