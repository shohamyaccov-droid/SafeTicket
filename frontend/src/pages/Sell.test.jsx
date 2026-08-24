import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import Sell from './Sell';
import { artistAPI, eventAPI, ticketAPI } from '../services/api';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'seller' },
    refreshProfile: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
  }),
}));

vi.mock('../services/api', () => ({
  ticketAPI: { createTicket: vi.fn() },
  eventAPI: { getEvents: vi.fn(), getEvent: vi.fn() },
  artistAPI: { getArtists: vi.fn() },
  eventRequestAPI: { create: vi.fn() },
}));

vi.mock('../utils/toast', () => ({
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock('../utils/analytics', () => ({
  Analytics: { ticketListed: vi.fn() },
}));

const SELL_DRAFT_STORAGE_KEY = 'safeticket_sell_listing_draft_v1';

const mockEvent = {
  id: 99,
  name: 'משחק בדיקה',
  category: 'sport',
  date: '2099-12-01T19:00:00Z',
  country: 'IL',
  venue: 'בלומפילד',
};

function seedStep2Draft() {
  sessionStorage.setItem(
    SELL_DRAFT_STORAGE_KEY,
    JSON.stringify({
      wizardStep: 2,
      selectedCategory: 'sport',
      selectedArtistId: '',
      uploadMethod: 'single_file',
      sellerListingTermsAccepted: false,
      formData: {
        event_id: 99,
        event_name: 'משחק בדיקה',
        section: 'דשא',
        row: '12',
        available_quantity: 1,
        is_together: true,
        start_seat: '1',
        listing_price: '',
        ticket_type: 'pdf',
        split_type: 'כל כמות',
        is_obstructed_view: false,
        allow_negotiation: true,
        ticket_packages: [{ seat_number: '' }],
      },
    }),
  );
}

function renderSell() {
  return render(
    <MemoryRouter>
      <Sell />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
});

describe('Sell wizard step 2 details', () => {
  beforeEach(() => {
    sessionStorage.clear();
    seedStep2Draft();
    Element.prototype.scrollIntoView = vi.fn();
    artistAPI.getArtists.mockResolvedValue({ data: [] });
    eventAPI.getEvents.mockResolvedValue({ data: [mockEvent] });
    eventAPI.getEvent.mockResolvedValue({ data: mockEvent });
    ticketAPI.createTicket.mockResolvedValue({ data: { id: 1 } });
  });

  it('keeps optional seating closed even when a draft already has section and row', async () => {
    renderSell();
    const toggle = await screen.findByRole('button', { name: '➕ הוספת פרטי ישיבה (אופציונלי)' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByLabelText('גוש (אופציונלי)')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('שורה (אופציונלי)')).not.toBeInTheDocument();
  });

  it('does not ask for ticket type and still validates price before publish', async () => {
    const user = userEvent.setup();
    renderSell();

    await screen.findByLabelText(/מחיר מכירה לכרטיס בודד/);
    expect(screen.queryByText('סוג כרטיס')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/סוג כרטיס/)).not.toBeInTheDocument();

    const price = screen.getByLabelText(/מחיר מכירה לכרטיס בודד/);
    const split = screen.getByLabelText(/אפשרויות פיצול/);
    const offers = screen.getByLabelText(/לאפשר לקונים להציע מחיר/);
    expect(price.compareDocumentPosition(split) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(split.compareDocumentPosition(offers) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    expect(
      screen.getByText(
        'זהו המחיר עבור כרטיס אחד שיוצג לקונים לפני עמלת ביטחון. (אם העלית מספר כרטיסים, המערכת תכפיל את הסכום אוטומטית).',
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText('אין צורך להזין מחיר מקורי או להעלות קבלה.')).not.toBeInTheDocument();

    expect(screen.queryByText(/פורמטים נתמכים/)).not.toBeInTheDocument();
    expect(screen.getByText('העלה קובץ PDF או תמונה, גודל מקסימלי 5MB לקובץ')).toBeInTheDocument();

    await user.click(screen.getByLabelText(/אני מאשר\/ת את/));
    await user.click(screen.getByRole('button', { name: 'פרסם כרטיס' }));

    expect(await screen.findByText('נא להזין מחיר מכירה.')).toBeInTheDocument();
    expect(ticketAPI.createTicket).not.toHaveBeenCalled();

    await user.type(price, '120');
    await user.click(screen.getByRole('button', { name: 'פרסם כרטיס' }));

    await waitFor(() => {
      expect(screen.getByText('אנא העלה קובץ כרטיס (PDF או תמונה).')).toBeInTheDocument();
    });
    expect(ticketAPI.createTicket).not.toHaveBeenCalled();
  });
});
