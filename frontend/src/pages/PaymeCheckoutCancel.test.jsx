import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import PaymeCheckoutCancel from './PaymeCheckoutCancel';
import { orderAPI, ticketAPI } from '../services/api';
import { toastSuccess } from '../utils/toast';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { id: 1 }, loading: false }),
}));

vi.mock('../services/api', () => ({
  orderAPI: { cancelPendingPayment: vi.fn() },
  ticketAPI: { unlockTicket: vi.fn() },
}));

vi.mock('../utils/toast', () => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock('../utils/checkoutGuest', () => ({
  clearPaymePendingOrder: vi.fn(),
}));

vi.mock('../utils/cartToken', () => ({
  getOrCreateCartToken: () => 'cart-token-test',
}));

function renderCancel(search = '?order_id=77&token=abc') {
  return render(
    <MemoryRouter initialEntries={[`/checkout/cancel${search}`]}>
      <Routes>
        <Route path="/checkout/cancel" element={<PaymeCheckoutCancel />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('PaymeCheckoutCancel', () => {
  beforeEach(() => {
    orderAPI.cancelPendingPayment.mockResolvedValue({
      data: { success: true, released: true, ticket_ids: [42], status: 'cancelled' },
    });
    ticketAPI.unlockTicket.mockResolvedValue({ data: { success: true } });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('cancels the pending order, unlocks tickets, and tells the buyer the seat is free', async () => {
    renderCancel();
    expect(await screen.findByRole('heading', { name: 'הכרטיס שוחרר' })).toBeInTheDocument();
    expect(orderAPI.cancelPendingPayment).toHaveBeenCalledWith(77, {
      guestEmail: undefined,
      paymentConfirmToken: 'abc',
    });
    expect(ticketAPI.unlockTicket).toHaveBeenCalledWith(42, null, 'cart-token-test');
    expect(toastSuccess).toHaveBeenCalled();
    expect(screen.getByText(/הכרטיס שוחרר וחזר למלאי/)).toBeInTheDocument();
  });
});
