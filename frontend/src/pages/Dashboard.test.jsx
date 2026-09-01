import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';

import Dashboard from './Dashboard';
import { authAPI, offerAPI, ticketAPI } from '../services/api';
import { toastError } from '../utils/toast';

vi.mock('../context/AuthContext', () => {
  const user = { id: 1, username: 'buyer' };
  return {
    useAuth: () => ({
      user,
      refreshProfile: vi.fn(),
    }),
  };
});

vi.mock('../services/api', () => ({
  authAPI: { getDashboard: vi.fn() },
  ticketAPI: { downloadPDF: vi.fn(), updateTicketPrice: vi.fn(), deleteTicket: vi.fn() },
  offerAPI: {
    getReceivedOffers: vi.fn(),
    getSentOffers: vi.fn(),
    acceptOffer: vi.fn(),
    rejectOffer: vi.fn(),
    counterOffer: vi.fn(),
  },
}));

vi.mock('../utils/toast', () => ({
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock('../utils/analytics', () => ({
  Analytics: { checkoutStart: vi.fn() },
}));

vi.mock('../utils/ticketDownload', () => ({
  downloadTicketFromAxiosBlob: vi.fn(),
}));

vi.mock('../components/CheckoutModal', () => ({ default: () => null }));
vi.mock('../components/NegotiationModal', () => ({ default: () => null }));
vi.mock('./ProfileWallet', () => ({ default: () => null }));
vi.mock('../components/BuyerIdentityInlineForm', () => ({ default: () => null }));

afterEach(() => {
  cleanup();
});

function paidPurchase(overrides = {}) {
  return {
    id: 101,
    status: 'paid',
    tickets: [],
    ticket_details: { event_name: 'הופעת בדיקה', event_date: '2099-01-01T20:00:00Z', venue: 'בלומפילד' },
    total_amount: 199,
    currency: 'ILS',
    quantity: 1,
    ...overrides,
  };
}

describe('Dashboard buyer order download', () => {
  beforeEach(() => {
    offerAPI.getReceivedOffers.mockResolvedValue({ data: [] });
    offerAPI.getSentOffers.mockResolvedValue({ data: [] });
    ticketAPI.downloadPDF.mockResolvedValue({ data: new Blob(['pdf']), headers: {} });
  });

  it('shows הורד כרטיס in the DOM for a paid ready order without tickets[]', async () => {
    authAPI.getDashboard.mockResolvedValue({
      data: {
        purchases: [paidPurchase({ ticket: 42 })],
        listings: { active: [], sold: [] },
        summary: { total_purchases: 1, active_listings_count: 0, sold_listings_count: 0 },
      },
    });

    render(
      <HelmetProvider>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </HelmetProvider>,
    );

    const button = await screen.findByRole('button', { name: 'הורד כרטיס' });
    expect(button).toBeInTheDocument();
    expect(button).toBeVisible();
    expect(screen.getByText('הזמנה אושרה')).toBeInTheDocument();
    expect(screen.getByText('תשלום אושר')).toBeInTheDocument();
    expect(screen.getByText('מוכן להורדה')).toBeInTheDocument();
  });

  it('shows הורד כרטיס for paid orders with only pdf_download_url', async () => {
    authAPI.getDashboard.mockResolvedValue({
      data: {
        purchases: [
          paidPurchase({
            pdf_download_url: 'https://example.com/api/users/tickets/77/download_pdf/',
          }),
        ],
        listings: { active: [], sold: [] },
        summary: { total_purchases: 1 },
      },
    });

    render(
      <HelmetProvider>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </HelmetProvider>,
    );

    expect(await screen.findByRole('button', { name: 'הורד כרטיס' })).toBeInTheDocument();
  });

  it('downloads via ticketAPI.downloadPDF when the button is clicked', async () => {
    const user = userEvent.setup();
    authAPI.getDashboard.mockResolvedValue({
      data: {
        purchases: [paidPurchase({ ticket: 42 })],
        listings: { active: [], sold: [] },
        summary: { total_purchases: 1 },
      },
    });

    render(
      <HelmetProvider>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </HelmetProvider>,
    );

    await user.click(await screen.findByRole('button', { name: 'הורד כרטיס' }));
    await waitFor(() => {
      expect(ticketAPI.downloadPDF).toHaveBeenCalledWith(42);
    });
  });

  it('downloads using ticket_ids when ticket FK is missing from the payload', async () => {
    const user = userEvent.setup();
    authAPI.getDashboard.mockResolvedValue({
      data: {
        purchases: [
          paidPurchase({
            ticket: null,
            ticket_ids: [64],
            tickets: [],
            pdf_download_url: null,
          }),
        ],
        listings: { active: [], sold: [] },
        summary: { total_purchases: 1 },
      },
    });

    render(
      <HelmetProvider>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </HelmetProvider>,
    );

    await user.click(await screen.findByRole('button', { name: 'הורד כרטיס' }));
    await waitFor(() => {
      expect(ticketAPI.downloadPDF).toHaveBeenCalledWith(64);
    });
  });

  it('shows section/row and seat from ticket_details instead of לא צוין', async () => {
    authAPI.getDashboard.mockResolvedValue({
      data: {
        purchases: [
          paidPurchase({
            ticket: 42,
            ticket_details: {
              event_name: 'הופעת בדיקה',
              event_date: '2099-01-01T20:00:00Z',
              venue: 'בלומפילד',
              section: '11',
              row: '4',
              seat_numbers: '18',
            },
          }),
        ],
        listings: { active: [], sold: [] },
        summary: { total_purchases: 1 },
      },
    });

    render(
      <HelmetProvider>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </HelmetProvider>,
    );

    expect(await screen.findByText(/גוש 11/)).toBeInTheDocument();
    expect(screen.getByText(/שורה 4/)).toBeInTheDocument();
    expect(screen.getByText('18')).toBeInTheDocument();
    expect(screen.queryByText('לא צוין')).not.toBeInTheDocument();
  });
});

describe('Dashboard sales inline price edit', () => {
  beforeEach(() => {
    offerAPI.getReceivedOffers.mockResolvedValue({ data: [] });
    offerAPI.getSentOffers.mockResolvedValue({ data: [] });
    ticketAPI.updateTicketPrice.mockReset();
  });

  function renderSalesDashboard() {
    authAPI.getDashboard.mockResolvedValue({
      data: {
        purchases: [],
        listings: {
          active: [
            {
              id: 42,
              status: 'active',
              event_name: 'הופעת מחיר',
              event_name_display: 'הופעת מחיר',
              original_price: '249.00',
              asking_price: '249.00',
              currency: 'ILS',
              available_quantity: 1,
              quantity: 1,
            },
          ],
          sold: [],
        },
        summary: { total_purchases: 0, active_listings_count: 1, sold_listings_count: 0 },
      },
    });
    return render(
      <HelmetProvider>
        <MemoryRouter initialEntries={['/dashboard?tab=sales']}>
          <Dashboard />
        </MemoryRouter>
      </HelmetProvider>,
    );
  }

  it('sends listing_price and original_price and surfaces the backend error', async () => {
    const user = userEvent.setup();
    ticketAPI.updateTicketPrice.mockRejectedValue({
      response: {
        status: 400,
        data: { error: 'לא ניתן לעדכן מחיר, משתמש אחר נמצא כרגע בתהליך רכישה.' },
      },
    });
    renderSalesDashboard();

    await user.click(await screen.findByText('הופעת מחיר'));
    await user.click(await screen.findByRole('button', { name: 'Edit price' }));
    const input = await screen.findByRole('spinbutton');
    await user.clear(input);
    await user.type(input, '220');
    await user.click(screen.getByRole('button', { name: 'שמור' }));

    await waitFor(() => {
      expect(ticketAPI.updateTicketPrice).toHaveBeenCalledWith(42, 220);
    });
    expect(toastError).toHaveBeenCalledWith(
      'לא ניתן לעדכן מחיר, משתמש אחר נמצא כרגע בתהליך רכישה.',
    );
  });
});
