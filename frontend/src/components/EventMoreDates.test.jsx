import { describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import EventMoreDates from './EventMoreDates';

describe('EventMoreDates', () => {
  const current = {
    id: 10,
    slug: 'show-13-10',
    name: 'אייל גולן',
    date: '2026-10-13T18:00:00Z',
  };

  it('renders date pills and the event-group CTA when sibling dates exist', () => {
    render(
      <MemoryRouter>
        <EventMoreDates
          event={current}
          relatedEvents={[
            current,
            { id: 11, slug: 'show-14-10', name: 'אייל גולן', date: '2026-10-14T18:00:00Z' },
          ]}
        />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: 'תאריכים נוספים' })).toBeInTheDocument();
    expect(screen.getByText('13.10')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '14.10' })).toHaveAttribute('href', '/event/show-14-10');
    expect(screen.getByRole('link', { name: 'צפה בכל התאריכים של אייל גולן' })).toHaveAttribute(
      'href',
      `/event-group/${encodeURIComponent('אייל גולן')}`
    );
  });

  it('hides when there is only one date', () => {
    const { container } = render(
      <MemoryRouter>
        <EventMoreDates event={current} relatedEvents={[current]} />
      </MemoryRouter>
    );
    expect(container).toBeEmptyDOMElement();
  });
});
