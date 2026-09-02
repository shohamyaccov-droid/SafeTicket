import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import EventCard from './EventCard';

const event = {
  id: 8,
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

describe('EventCard last-minute waitlist CTA', () => {
  it('shows seller waitlist CTA below tickets and does not open the event on CTA click', async () => {
    const user = userEvent.setup();
    const { onNavigate } = renderCard();
    const cta = screen.getByRole('link', { name: /5 אנשים מחכים/ });
    expect(cta).toHaveAttribute('href', '/sell/new?event=8');
    await user.click(cta);
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it('hides the waitlist CTA when nobody is waiting', () => {
    renderCard({ event: { ...event, waitlist_count: 0 } });
    expect(screen.queryByRole('link', { name: /רשימת ההמתנה/ })).not.toBeInTheDocument();
  });

  it('does not show the waitlist CTA on default homepage cards', () => {
    renderCard({ variant: 'default' });
    expect(screen.queryByRole('link', { name: /רשימת ההמתנה/ })).not.toBeInTheDocument();
  });
});
