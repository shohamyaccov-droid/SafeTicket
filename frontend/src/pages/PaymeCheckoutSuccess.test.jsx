import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import PaymeCheckoutSuccess from './PaymeCheckoutSuccess';
import { orderAPI } from '../services/api';
import { Analytics } from '../utils/analytics';
import { trackGoogleAdsPurchase } from '../utils/googleAdsConversions';
import { trackMetaPurchase } from '../utils/metaPixel';
import { downloadTicketFromAxiosBlob } from '../utils/ticketDownload';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: null, loading: false }),
}));

vi.mock('../services/api', () => ({
  orderAPI: { getReceipt: vi.fn(), getPaymentStatus: vi.fn(), downloadTickets: vi.fn() },
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

vi.mock('../utils/ticketDownload', () => ({
  downloadTicketFromAxiosBlob: vi.fn(),
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

describe('PaymeCheckoutSuccess purchase attribution', () => {
  beforeEach(() => {
    vi.mocked(orderAPI.getPaymentStatus).mockReset();
    vi.mocked(orderAPI.getReceipt).mockReset();
    vi.mocked(orderAPI.downloadTickets).mockReset();
    vi.mocked(downloadTicketFromAxiosBlob).mockReset();
    vi.mocked(trackGoogleAdsPurchase).mockClear();
    vi.mocked(trackMetaPurchase).mockClear();
    vi.mocked(Analytics.checkoutComplete).mockClear();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('does not fire Purchase while PayMe is still processing', async () => {
    vi.mocked(orderAPI.getPaymentStatus).mockResolvedValue({
      data: { status: 'pending_payment', payme_status: 'pending' },
    });
    renderSuccess();
    expect(await screen.findByRole('heading', { name: 'מעבדים את התשלום...' })).toBeInTheDocument();
    expect(trackGoogleAdsPurchase).not.toHaveBeenCalled();
    expect(Analytics.checkoutComplete).not.toHaveBeenCalled();
  });

  it('fires Purchase once with paid amount and order id after PayMe confirms', async () => {
    vi.mocked(orderAPI.getPaymentStatus).mockResolvedValue({
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
    expect(Analytics.checkoutComplete).toHaveBeenCalledWith(42, {
      value: 187.5,
      currency: 'ILS',
    });
    expect(trackMetaPurchase).toHaveBeenCalledWith({
      orderId: 42,
      value: 187.5,
      currency: 'ILS',
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

  it('shows safe success after soft timeout but keeps polling until paid', async () => {
    vi.useFakeTimers();
    vi.mocked(orderAPI.getPaymentStatus).mockResolvedValue({
      data: { status: 'pending_payment', payme_status: 'pending', total_amount: '100' },
    });
    renderSuccess();
    expect(screen.getByRole('heading', { name: 'מעבדים את התשלום...' })).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });
    expect(
      screen.getByText(
        'התשלום התקבל בהצלחה! אנחנו מפיקים את הכרטיס והוא יישלח אליך למייל בדקות הקרובות.',
      ),
    ).toBeInTheDocument();
    expect(Analytics.checkoutComplete).not.toHaveBeenCalled();

    vi.mocked(orderAPI.getPaymentStatus).mockResolvedValue({
      data: {
        status: 'paid',
        total_paid_by_buyer: 100,
        currency: 'ILS',
        download_token: 'dl',
      },
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(screen.getByRole('heading', { name: 'התשלום הושלם בהצלחה!' })).toBeInTheDocument();
    expect(Analytics.checkoutComplete).toHaveBeenCalledWith(42, {
      value: 100,
      currency: 'ILS',
    });
  });

  it('fires purchase when payme_status is success even if order is still pending', async () => {
    vi.mocked(orderAPI.getPaymentStatus).mockResolvedValue({
      data: {
        status: 'pending_payment',
        payme_status: 'success',
        total_paid_by_buyer: 210,
        currency: 'ILS',
      },
    });
    renderSuccess();
    await waitFor(() => {
      expect(Analytics.checkoutComplete).toHaveBeenCalledWith(42, {
        value: 210,
        currency: 'ILS',
      });
    });
    expect(trackMetaPurchase).toHaveBeenCalled();
  });

  it('treats a hung status poll as safe success instead of logging out', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(orderAPI.getPaymentStatus).mockImplementation(
      () =>
        new Promise((_, reject) => {
          const err = new Error('timeout of 8000ms exceeded');
          err.code = 'ECONNABORTED';
          window.setTimeout(() => reject(err), 8000);
        }),
    );
    renderSuccess();
    expect(screen.getByRole('heading', { name: 'מעבדים את התשלום...' })).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });
    expect(
      screen.getByText(
        'התשלום התקבל בהצלחה! אנחנו מפיקים את הכרטיס והוא יישלח אליך למייל בדקות הקרובות.',
      ),
    ).toBeInTheDocument();
  });

  it('shows download tickets button after paid confirmation and fetches the bulk file', async () => {
    const blobResponse = { data: new Blob(['pdf']), headers: { 'content-type': 'application/pdf' } };
    vi.mocked(orderAPI.getPaymentStatus).mockResolvedValue({
      data: {
        status: 'paid',
        total_paid_by_buyer: 187.5,
        currency: 'ILS',
        download_token: 'signed-dl',
      },
    });
    vi.mocked(orderAPI.downloadTickets).mockResolvedValue(blobResponse);
    renderSuccess();
    const button = await screen.findByRole('button', { name: 'הורד כרטיסים עכשיו' });
    fireEvent.click(button);
    await waitFor(() => {
      expect(orderAPI.downloadTickets).toHaveBeenCalledWith(42, {
        guestEmail: undefined,
        downloadToken: 'signed-dl',
      });
    });
    expect(downloadTicketFromAxiosBlob).toHaveBeenCalledWith(blobResponse, { ticketId: 'order-42' });
  });
});
