import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import CheckoutModal from './CheckoutModal';
import { orderAPI, paymentAPI, ticketAPI } from '../services/api';

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ refreshProfile: vi.fn() }),
}));

vi.mock('../context/AuthModalContext', () => ({
  useAuthModal: () => ({ openLogin: vi.fn(), openRegister: vi.fn() }),
}));

vi.mock('../hooks/useBuyerServiceFeePercent', () => ({
  usePricingSettings: () => ({ serviceFeePercent: 7 }),
  default: () => 7,
}));

vi.mock('../hooks/useBodyScrollLock', () => ({
  useBodyScrollLock: () => {},
}));

vi.mock('../hooks/useFocusScrollIntoView', () => ({
  default: () => {},
}));

vi.mock('../hooks/useVisualViewportInset', () => ({
  default: () => {},
}));

vi.mock('../utils/toast', () => ({
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock('../utils/analytics', () => ({
  Analytics: { checkoutStart: vi.fn(), checkoutComplete: vi.fn() },
}));

vi.mock('../services/api', () => ({
  authAPI: { getCsrf: vi.fn().mockResolvedValue({}) },
  orderAPI: {
    createOrder: vi.fn(),
    guestCheckout: vi.fn(),
    confirmPayment: vi.fn(),
    validateCoupon: vi.fn(),
  },
  paymentAPI: {
    getShabbatStatus: vi.fn(),
    simulatePayment: vi.fn(),
    mockPaymentSuccess: vi.fn(),
    paymeInitCheckout: vi.fn(),
  },
  ticketAPI: {
    reserveTicket: vi.fn(),
    releaseReservation: vi.fn(),
    releaseReservationKeepalive: vi.fn(),
    downloadPDF: vi.fn(),
  },
  ensureCsrfToken: vi.fn().mockResolvedValue(undefined),
  getEffectiveBearerAccess: vi.fn().mockReturnValue('test-access-token'),
  syncAxiosDefaultAuthHeader: vi.fn(),
  notifySessionExpired: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

const ticket = {
  id: 42,
  asking_price: 100,
  original_price: 100,
  listing_price: 100,
  available_quantity: 1,
  status: 'reserved',
  event_name: 'הופעת בדיקה',
  currency: 'ILS',
};

const buyer = {
  id: 7,
  username: 'buyer',
  email: 'buyer@example.com',
  first_name: 'ישראל',
  last_name: 'ישראלי',
  phone_number: '0500000000',
};

function renderCheckout(onClose = vi.fn()) {
  const view = render(
    <MemoryRouter>
      <CheckoutModal ticket={ticket} user={buyer} onClose={onClose} />
    </MemoryRouter>,
  );
  return { ...view, onClose };
}

async function acceptTermsAndFindPayButton() {
  const payBtn = await screen.findByRole('button', { name: 'המשך לתשלום' });
  const tos = screen.getByRole('checkbox');
  if (!tos.checked) {
    await userEvent.click(tos);
  }
  await waitFor(() => expect(payBtn).toBeEnabled());
  return payBtn;
}

beforeEach(() => {
  ticketAPI.reserveTicket.mockResolvedValue({ data: { success: true } });
  ticketAPI.releaseReservation.mockResolvedValue({ data: { success: true } });
  paymentAPI.getShabbatStatus.mockResolvedValue({ data: { is_shabbat: false } });
  paymentAPI.mockPaymentSuccess.mockResolvedValue({ data: { finalized: true } });
  orderAPI.createOrder.mockResolvedValue({ data: { id: 77 } });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('CheckoutModal submit lock', () => {
  it('fires a single create-order POST when Pay is multi-tapped', async () => {
    let resolveCreate;
    orderAPI.createOrder.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve;
        }),
    );

    renderCheckout();
    const payBtn = await acceptTermsAndFindPayButton();

    fireEvent.click(payBtn);
    fireEvent.click(payBtn);
    fireEvent.click(payBtn);
    fireEvent.click(payBtn);
    fireEvent.click(payBtn);

    await waitFor(() => expect(orderAPI.createOrder).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('button', { name: /מעביר ל-PayMe/ })).toBeDisabled();

    resolveCreate({ data: { id: 77 } });
    await waitFor(() => expect(paymentAPI.mockPaymentSuccess).toHaveBeenCalledTimes(1));
    expect(orderAPI.createOrder).toHaveBeenCalledTimes(1);
  });

  it('unlocks the Pay button and shows a connection error after a timeout', async () => {
    const timeoutErr = Object.assign(new Error('timeout of 15000ms exceeded'), {
      code: 'ECONNABORTED',
    });
    orderAPI.createOrder.mockRejectedValue(timeoutErr);

    renderCheckout();
    const payBtn = await acceptTermsAndFindPayButton();
    fireEvent.click(payBtn);

    expect(
      await screen.findByText('יש בעיית חיבור לשרת. בדקו את האינטרנט ונסו שוב.'),
    ).toBeInTheDocument();

    const unlocked = await screen.findByRole('button', { name: 'המשך לתשלום' });
    await waitFor(() => expect(unlocked).toBeEnabled());
    expect(orderAPI.createOrder).toHaveBeenCalledTimes(1);
  });
});

describe('CheckoutModal coupon field', () => {
  it('does not close the modal when the coupon input is clicked or typed into', async () => {
    const { onClose } = renderCheckout();
    const input = await screen.findByPlaceholderText('הזן קוד קופון');

    await userEvent.click(input);
    await userEvent.type(input, 'SAVE10');

    expect(input).toHaveValue('SAVE10');
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByText('סיכום והמשך לתשלום')).toBeInTheDocument();
  });

  it('does not close or submit checkout when Enter is pressed in the coupon field', async () => {
    orderAPI.validateCoupon.mockResolvedValue({
      data: {
        code: 'SAVE10',
        discount_type: 'percentage',
        total_amount: '100.00',
      },
    });
    const { onClose } = renderCheckout();
    const input = await screen.findByPlaceholderText('הזן קוד קופון');

    await userEvent.click(input);
    await userEvent.type(input, 'SAVE10{enter}');

    await waitFor(() => expect(orderAPI.validateCoupon).toHaveBeenCalledTimes(1));
    expect(onClose).not.toHaveBeenCalled();
    expect(orderAPI.createOrder).not.toHaveBeenCalled();
    expect(screen.getByText('סיכום והמשך לתשלום')).toBeInTheDocument();
  });

  it('does not close when a click completes on the overlay after pointerdown on the coupon input', async () => {
    const { onClose } = renderCheckout();
    const input = await screen.findByPlaceholderText('הזן קוד קופון');
    const overlay = document.querySelector('.checkout-modal-overlay');
    expect(overlay).toBeTruthy();

    fireEvent.pointerDown(input);
    fireEvent.click(overlay);

    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByPlaceholderText('הזן קוד קופון')).toBeInTheDocument();
  });

  it('shows full 7% service fee plus a separate coupon line', async () => {
    orderAPI.validateCoupon.mockResolvedValue({
      data: {
        code: 'SAVE20',
        discount_type: 'fixed',
        fixed_discount_amount: '20.00',
        total_amount: '512.86',
      },
    });
    render(
      <MemoryRouter>
        <CheckoutModal
          ticket={{
            ...ticket,
            asking_price: 249,
            original_price: 249,
            listing_price: 249,
            available_quantity: 2,
          }}
          ticketGroup={{ available_count: 2, tickets: [{ ...ticket, asking_price: 249, status: 'active', available_quantity: 1 }] }}
          user={buyer}
          quantity={2}
          onClose={vi.fn()}
        />
      </MemoryRouter>,
    );
    expect(await screen.findByText('מחיר כרטיסים')).toBeInTheDocument();
    const input = await screen.findByPlaceholderText('הזן קוד קופון');
    await userEvent.type(input, 'SAVE20');
    await userEvent.click(screen.getByRole('button', { name: 'הפעל' }));
    await waitFor(() => expect(orderAPI.validateCoupon).toHaveBeenCalled());
    expect(screen.getByText('דמי שירות ותפעול (7%)').closest('.price-row')).toHaveTextContent('34.86');
    expect(screen.queryByText(/14\.86/)).not.toBeInTheDocument();
    expect(screen.getByText(/הנחת קופון/).closest('.price-row')).toHaveTextContent('20');
    expect(screen.getByText('סך הכל לתשלום:').closest('.price-row')).toHaveTextContent('512.86');
  });
});

describe('CheckoutModal cart unlock', () => {
  it('releases the hold when the X button is clicked', async () => {
    const { onClose } = renderCheckout();
    await screen.findByRole('button', { name: 'המשך לתשלום' });
    await userEvent.click(screen.getByRole('button', { name: 'סגירה' }));
    await waitFor(() => expect(ticketAPI.releaseReservationKeepalive).toHaveBeenCalled());
    expect(onClose).toHaveBeenCalled();
  });

  it('releases the hold when ביטול is clicked', async () => {
    const { onClose } = renderCheckout();
    await screen.findByRole('button', { name: 'ביטול' });
    await userEvent.click(screen.getByRole('button', { name: 'ביטול' }));
    await waitFor(() => expect(ticketAPI.releaseReservationKeepalive).toHaveBeenCalled());
    expect(onClose).toHaveBeenCalled();
  });
});
