import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import PaymeCheckoutSuccess from './PaymeCheckoutSuccess';
import { orderAPI } from '../services/api';
import { trackGoogleAdsPurchase } from '../utils/googleAdsConversions';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: null, loading: false }),
}));

vi.mock('../services/api', () => ({
  orderAPI: { getReceipt: vi.fn() },
}));

vi.mock('../utils/analytics', () => ({
  Analytics: { checkoutComplete: vi.fn() },
}));

vi.mock('../utils/checkoutGuest', () => ({
  clearPaymePendingOrder: vi.fn(),
}));

vi.mock('../utils/googleAdsConversions', () => ({
  trackGoogleAdsPurchase: vi.fn(),
}));

vi.mock('../utils/metaPixel', () => ({
  trackMetaPurchase: vi.fn(),
}));

function renderSuccess(search = '?order_id=42') {
  return render(
    <MemoryRouter initialEntries={[`/checkout/payme/success${search}`]}>
      <Routes>
        <Route path="/checkout/payme/success" element={<PaymeCheckoutSuccess />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('PaymeCheckoutSuccess Google Ads Purchase', () => {
  beforeEach(() => {
    vi.mocked(orderAPI.getReceipt).mockReset();
    vi.mocked(trackGoogleAdsPurchase).mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('does not fire Purchase while PayMe is still processing', async () => {
    vi.mocked(orderAPI.getReceipt).mockResolvedValue({
      data: { status: 'pending_payment', payme_status: 'pending' },
    });
    renderSuccess();
    expect(await screen.findByRole('heading', { name: 'מעבדים את התשלום...' })).toBeInTheDocument();
    expect(trackGoogleAdsPurchase).not.toHaveBeenCalled();
  });

  it('fires Purchase once with paid amount and order id after PayMe confirms', async () => {
    vi.mocked(orderAPI.getReceipt).mockResolvedValue({
      data: {
        status: 'paid',
        total_paid_by_buyer: 187.5,
        currency: 'ILS',
      },
    });
    renderSuccess();
    expect(await screen.findByRole('heading', { name: 'התשלום הושלם בהצלחה!' })).toBeInTheDocument();
    await waitFor(() => {
      expect(trackGoogleAdsPurchase).toHaveBeenCalledTimes(1);
    });
    expect(trackGoogleAdsPurchase).toHaveBeenCalledWith({
      value: 187.5,
      transactionId: '42',
      currency: 'ILS',
    });
  });

  it('does not fire Purchase on an invalid success URL', async () => {
    renderSuccess('');
    expect(await screen.findByRole('heading', { name: 'קישור לא תקין' })).toBeInTheDocument();
    expect(trackGoogleAdsPurchase).not.toHaveBeenCalled();
  });
});
