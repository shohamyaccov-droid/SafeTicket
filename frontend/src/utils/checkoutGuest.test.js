import { afterEach, describe, expect, it } from 'vitest';
import {
  clearPaymePendingOrder,
  guestCanReserveCart,
  guestHasCheckoutEmail,
  isGuestEmailRequiredError,
  readPaymePendingOrder,
  shouldRescuePaymeReturn,
  stashPaymePendingOrder,
} from './checkoutGuest';

afterEach(() => {
  clearPaymePendingOrder();
});


describe('checkoutGuest', () => {
  it('treats logged-in buyers as ready without an email field', () => {
    expect(guestHasCheckoutEmail({ id: 1 }, '')).toBe(true);
  });

  it('requires a guest email before reserving the cart', () => {
    expect(guestHasCheckoutEmail(null, '')).toBe(false);
    expect(guestHasCheckoutEmail(null, '  ')).toBe(false);
    expect(guestHasCheckoutEmail(null, 'buyer@example.com')).toBe(true);
  });

  it('allows a cart token to lock before the guest types an email', () => {
    expect(guestCanReserveCart(null, '', 'abc')).toBe(true);
    expect(guestCanReserveCart(null, '', '')).toBe(false);
    expect(guestCanReserveCart({ id: 1 }, '', '')).toBe(true);
  });

  it('detects guest_email_required without showing a crash banner', () => {
    expect(
      isGuestEmailRequiredError({
        response: { data: { code: 'guest_email_required', error: 'נדרש אימייל כדי לשמור את הכרטיס בעגלה.' } },
      }),
    ).toBe(true);
    expect(isGuestEmailRequiredError({ response: { data: { error: 'held_by_other' } } })).toBe(false);
  });

  it('rescues a PayMe return that landed on home within 45 minutes', () => {
    stashPaymePendingOrder(42);
    const pending = readPaymePendingOrder();
    expect(pending?.id).toBe(42);
    expect(shouldRescuePaymeReturn('/', 'https://live.payme.io/done', pending)).toBe(true);
    expect(shouldRescuePaymeReturn('/checkout/payme/success', 'https://live.payme.io/done', pending)).toBe(false);
    expect(shouldRescuePaymeReturn('/event/itay-levi-2026-09-01', '', pending)).toBe(false);
  });
});

