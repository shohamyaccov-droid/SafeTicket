import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';

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
  Analytics: { ticketListed: vi.fn(), beginTicketUpload: vi.fn() },
  isListingCreateHttpSuccess: (res) => {
    const status = res?.status;
    if (status == null) return Boolean(res?.data);
    const n = Number(status);
    return Number.isFinite(n) && n >= 200 && n < 300;
  },
  listingIdFromCreateResponse: (data) => data?.id ?? null,
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
    <HelmetProvider>
      <MemoryRouter>
        <Sell />
      </MemoryRouter>
    </HelmetProvider>,
  );
}

async function fillValidListing() {
  const user = userEvent.setup();
  const price = await screen.findByLabelText(/מחיר מכירה לכרטיס בודד/);
  await user.type(price, '150');
  const file = new File(['%PDF-1.4 lock-test'], 'ticket.pdf', { type: 'application/pdf' });
  await user.upload(screen.getByLabelText(/קובץ כרטיס \(PDF או תמונה\)/), file);
  await user.click(screen.getByLabelText(/אני מאשר\/ת את/));
  return screen.getByRole('button', { name: 'פרסם כרטיס' });
}

beforeEach(() => {
  sessionStorage.clear();
  seedStep2Draft();
  Element.prototype.scrollIntoView = vi.fn();
  artistAPI.getArtists.mockResolvedValue({ data: [] });
  eventAPI.getEvents.mockResolvedValue({ data: [mockEvent] });
  eventAPI.getEvent.mockResolvedValue({ data: mockEvent });
  ticketAPI.createTicket.mockResolvedValue({ status: 201, data: { id: 9 } });
});

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.clearAllMocks();
});

describe('Sell /sell/new submit lock', () => {
  it('fires a single createTicket POST when Publish is multi-tapped', async () => {
    let resolveCreate;
    ticketAPI.createTicket.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve;
        }),
    );

    renderSell();
    const publish = await fillValidListing();

    fireEvent.click(publish);
    fireEvent.click(publish);
    fireEvent.click(publish);
    fireEvent.click(publish);
    fireEvent.click(publish);

    await waitFor(() => expect(ticketAPI.createTicket).toHaveBeenCalledTimes(1));
    expect(screen.getByText('מעלה את הכרטיס...')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /מפרסם כרטיס/ }).every((btn) => btn.disabled)).toBe(true);

    resolveCreate({ status: 201, data: { id: 9 } });
    await waitFor(() => expect(ticketAPI.createTicket).toHaveBeenCalledTimes(1));
  });

  it('unlocks publish and shows a connection error after a timeout', async () => {
    const timeoutErr = Object.assign(new Error('timeout of 15000ms exceeded'), {
      code: 'ECONNABORTED',
    });
    ticketAPI.createTicket.mockRejectedValue(timeoutErr);

    renderSell();
    const publish = await fillValidListing();
    fireEvent.click(publish);

    expect(
      await screen.findByText('יש בעיית חיבור לשרת. בדקו את האינטרנט ונסו שוב.'),
    ).toBeInTheDocument();

    const unlocked = await screen.findByRole('button', { name: 'פרסם כרטיס' });
    await waitFor(() => expect(unlocked).toBeEnabled());
    expect(ticketAPI.createTicket).toHaveBeenCalledTimes(1);
  });
});
