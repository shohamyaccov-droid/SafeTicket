import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import AdminOffersPage from './AdminOffersPage';
import { adminAPI } from '../services/api';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'admin', is_staff: true } }),
}));

vi.mock('../services/api', () => ({
  adminAPI: {
    getOffersDashboard: vi.fn(),
  },
}));

vi.mock('../utils/toast', () => ({
  toastError: vi.fn(),
}));

const payload = {
  metrics: {
    total_offers: 3,
    total_conversations: 2,
    status_counts: { pending: 1, accepted: 1, rejected: 1, countered: 0, expired: 0 },
    unique_buyers: 2,
    unique_sellers: 1,
    response_rate_percent: '50.00',
    acceptance_rate_percent: '50.00',
    purchase_conversion_percent: '100.00',
    accepted_offers: 1,
    completed_purchases: 1,
    countered_conversations: 1,
    by_currency: [{ currency: 'ILS', count: 3, average_amount: '150.00' }],
    daily_activity: Array.from({ length: 14 }, (_value, index) => ({
      date: `2026-07-${String(index + 1).padStart(2, '0')}`,
      count: index === 13 ? 3 : 0,
    })),
  },
  count: 1,
  page: 1,
  page_size: 50,
  results: [
    {
      id: 12,
      conversation_id: 10,
      buyer: { username: 'buyer', email: 'buyer@example.com' },
      seller: { username: 'seller', email: 'seller@example.com' },
      sender_username: 'buyer',
      ticket_id: 99,
      event_name: 'Test Concert',
      amount: '150.00',
      asking_total: '200.00',
      discount_percent: '25.00',
      currency: 'ILS',
      quantity: 2,
      status: 'accepted',
      round: 0,
      purchase_completed: true,
      order_id: 44,
      created_at: '2026-07-20T10:00:00Z',
    },
  ],
};

describe('AdminOffersPage', () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    adminAPI.getOffersDashboard.mockReset();
    adminAPI.getOffersDashboard.mockResolvedValue({ data: payload });
  });

  it('renders engagement metrics and tracked offer outcomes', async () => {
    render(
      <MemoryRouter>
        <AdminOffersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Test Concert')).toBeInTheDocument();
    expect(screen.getByText('100.00%')).toBeInTheDocument();
    expect(screen.getByText('נרכשה · הזמנה #44')).toBeInTheDocument();
    expect(screen.getByText('25.00% הנחה')).toBeInTheDocument();
    expect(adminAPI.getOffersDashboard).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'all', days: '30', page: 1 }),
    );
  });

  it('requests server-side filtering when status changes', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AdminOffersPage />
      </MemoryRouter>,
    );
    await screen.findByText('Test Concert');

    await user.selectOptions(screen.getByLabelText('סטטוס'), 'accepted');
    await waitFor(() => {
      expect(adminAPI.getOffersDashboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: 'accepted' }),
      );
    });
  });
});
