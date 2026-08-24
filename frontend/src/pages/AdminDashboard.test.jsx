import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import AdminDashboard from './AdminDashboard';
import { adminAPI } from '../services/api';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { username: 'admin', is_staff: true, is_superuser: true } }),
}));

vi.mock('../services/api', () => ({
  adminAPI: {
    getDashboardStats: vi.fn(),
    getTransactions: vi.fn(),
    getPendingTickets: vi.fn(),
    approveTicket: vi.fn(),
    updateTicketSeating: vi.fn(),
    rejectTicket: vi.fn(),
    cancelOrder: vi.fn(),
  },
  ticketAPI: { downloadReceipt: vi.fn() },
  ensureCsrfToken: vi.fn(),
}));

vi.mock('../utils/toast', () => ({
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock('../components/Ga4AnalyticsDashboard', () => ({
  default: () => null,
}));

afterEach(() => {
  cleanup();
});

describe('AdminDashboard pending quick seating', () => {
  beforeEach(() => {
    adminAPI.getDashboardStats.mockResolvedValue({
      data: { today: { tickets_sold: 0, by_currency: {} }, all_time: { tickets_sold: 0, by_currency: {} } },
    });
    adminAPI.getTransactions.mockResolvedValue({ data: { transactions: [] } });
    adminAPI.getPendingTickets.mockResolvedValue({
      data: {
        tickets: [
          {
            id: 42,
            event_name: 'הופעה',
            section: '',
            row: '',
            original_price: 100,
            asking_price: 100,
            ticket_file_url: 'https://example.test/ticket.pdf',
          },
        ],
      },
    });
    adminAPI.updateTicketSeating.mockResolvedValue({
      data: { ticket: { id: 42, section: 'דשא', row: '2' } },
    });
    adminAPI.approveTicket.mockResolvedValue({ data: { ticket: { id: 42, status: 'active' } } });
  });

  it('saves section and row from the pending list, then sends them on approve', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole('button', { name: /ממתין לאימות \(1\)/ }));
    await screen.findByLabelText('גוש');
    await user.type(screen.getByLabelText('גוש'), 'דשא');
    await user.type(screen.getByLabelText('שורה'), '2');
    await user.click(screen.getByRole('button', { name: 'שמור' }));

    await waitFor(() => {
      expect(adminAPI.updateTicketSeating).toHaveBeenCalledWith(42, { section: 'דשא', row: '2' });
    });

    await user.click(screen.getByRole('button', { name: 'שחרר לאתר' }));
    await waitFor(() => {
      expect(adminAPI.approveTicket).toHaveBeenCalledWith(42, { section: 'דשא', row: '2' });
    });
  });
});
