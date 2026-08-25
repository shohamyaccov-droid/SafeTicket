/** Guest checkout identity helpers. */

export function guestHasCheckoutEmail(user, guestEmail) {
  if (user) return true;
  return Boolean(String(guestEmail || '').trim());
}

export function guestCanReserveCart(user, guestEmail, cartToken) {
  if (user) return true;
  if (String(guestEmail || '').trim()) return true;
  return Boolean(String(cartToken || '').trim());
}

export function isGuestEmailRequiredError(err) {
  const data = err?.response?.data ?? err?.data ?? err;
  const code = data?.code;
  const text = `${code || ''} ${data?.error || ''} ${data?.detail || ''} ${err?.message || ''}`;
  return code === 'guest_email_required' || /guest_email_required|נדרש אימייל כדי לשמור/.test(text);
}
