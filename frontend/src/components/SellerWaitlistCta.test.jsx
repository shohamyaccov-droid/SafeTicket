import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SellerWaitlistCta from './SellerWaitlistCta';

describe('SellerWaitlistCta', () => {
  it('renders nothing when waitlist_count is missing or zero', () => {
    const { container: missing } = render(
      <MemoryRouter>
        <SellerWaitlistCta event={{ id: 1 }} />
      </MemoryRouter>,
    );
    expect(missing).toBeEmptyDOMElement();

    const { container: zero } = render(
      <MemoryRouter>
        <SellerWaitlistCta event={{ id: 1, waitlist_count: 0 }} />
      </MemoryRouter>,
    );
    expect(zero).toBeEmptyDOMElement();
  });

  it('links to the sell flow with the event preselected', () => {
    render(
      <MemoryRouter>
        <SellerWaitlistCta event={{ id: 42, waitlist_count: 7 }} />
      </MemoryRouter>,
    );
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/sell/new?event=42');
    expect(link).toHaveTextContent('7 אנשים מחכים');
    expect(link).toHaveTextContent('לחץ כאן למכירה מהירה');
  });
});
