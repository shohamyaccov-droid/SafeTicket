import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import EventCard from './EventCard';

const event = {
  id: 8,
  slug: 'last-show',
  name: 'הופעה אחרונה',
  date: '2026-09-10T20:00:00+03:00',
  venue: 'בלומפילד',
  city: 'תל אביב',
  waitlist_count: 5,
};

function renderCard(props = {}) {
  const onNavigate = vi.fn();
  const view = render(
    <MemoryRouter>
      <EventCard
        event={event}
        formatEventDateHe={() => '10 בספטמבר'}
        onNavigate={onNavigate}
        variant="lastMinute"
        {...props}
      />
    </MemoryRouter>,
  );
  return { ...view, onNavigate };
}

describe('EventCard dual CTAs and FOMO', () => {
  it('shows buy and sell links without navigating the card on sell click', async () => {
    const user = userEvent.setup();
    const { onNavigate } = renderCard({ variant: 'default' });
    const buy = screen.getByRole('link', { name: 'לרכישת כרטיסים' });
    const sell = screen.getByRole('link', { name: 'מכירת כרטיס' });
    expect(buy).toHaveAttribute('href', '/event/last-show');
    expect(sell).toHaveAttribute('href', '/sell/new?event=8');
    await user.click(sell);
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it('shows the event title, city, and upcoming-date count from the event', () => {
    renderCard({ variant: 'default', hasListings: true });
    expect(screen.getByText('הופעה אחרונה')).toBeInTheDocument();
    expect(screen.getByText('תל אביב')).toBeInTheDocument();
    expect(screen.getByText('מועדים קרובים')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('drops a repeated city from the visible title and keeps the city line', () => {
    renderCard({
      event: { ...event, name: 'היסטריה - ירושלים', city: 'ירושלים' },
    });
    expect(screen.getByText('היסטריה')).toBeInTheDocument();
    expect(screen.getByText('ירושלים')).toBeInTheDocument();
    expect(screen.queryByText('היסטריה - ירושלים')).not.toBeInTheDocument();
  });
});
