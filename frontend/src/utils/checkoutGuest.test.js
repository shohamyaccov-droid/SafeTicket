import { describe, expect, it } from 'vitest';
import { guestHasCheckoutEmail, isGuestEmailRequiredError } from './checkoutGuest';

describe('checkoutGuest', () => {
  it('treats logged-in buyers as ready without an email field', () => {
    expect(guestHasCheckoutEmail({ id: 1 }, '')).toBe(true);
  });

  it('requires a guest email before reserving the cart', () => {
    expect(guestHasCheckoutEmail(null, '')).toBe(false);
    expect(guestHasCheckoutEmail(null, '  ')).toBe(false);
    expect(guestHasCheckoutEmail(null, 'buyer@example.com')).toBe(true);
  });

  it('detects guest_email_required without showing a crash banner', () => {
    expect(
      isGuestEmailRequiredError({
        response: { data: { code: 'guest_email_required', error: 'נדרש אימייל כדי לשמור את הכרטיס בעגלה.' } },
      }),
    ).toBe(true);
    expect(isGuestEmailRequiredError({ response: { data: { error: 'held_by_other' } } })).toBe(false);
  });
});
