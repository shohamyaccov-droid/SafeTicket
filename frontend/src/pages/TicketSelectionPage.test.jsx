import { describe, expect, it, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

import TicketSelectionPage from './TicketSelectionPage';
import { ticketAPI } from '../services/api';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { id: 7, username: 'buyer' } }),
}));

vi.mock('../services/api', () => ({
  ticketAPI: {
    getTicket: vi.fn(),
    getTickets: vi.fn(),
  },
}));

vi.mock('../hooks/useBuyerServiceFeePercent', () => ({
  default: () => 7,
}));

vi.mock('../components/CheckoutModal', () => ({
  default: () => null,
}));

vi.mock('../utils/toast', () => ({
  toastError: vi.fn(),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ ticketId: '123' }),
    useNavigate: () => vi.fn(),
    useLocation: () => ({ state: { eventId: 99 } }),
  };
});

const ticketPayload = {
  id: 123,
  event_id: 99,
  event_name: 'QA Concert',
  event_date: '2026-08-20T19:00:00Z',
  venue: 'Menora Arena',
  available_quantity: 3,
  original_price: '100.00',
  asking_price: '100.00',
  is_together: true,
};

describe('TicketSelectionPage', () => {
  beforeEach(() => {
    ticketAPI.getTicket.mockReset();
    ticketAPI.getTickets.mockReset();
    ticketAPI.getTicket.mockResolvedValue({ data: ticketPayload });
  });

  it('loads a single ticket by id instead of fetching the full tickets list', async () => {
    render(<TicketSelectionPage />);

    expect(await screen.findByRole('heading', { name: 'QA Concert' })).toBeInTheDocument();
    await waitFor(() => {
      expect(ticketAPI.getTicket).toHaveBeenCalledWith('123', expect.any(Object));
    });
    expect(ticketAPI.getTickets).not.toHaveBeenCalled();
  });
});
