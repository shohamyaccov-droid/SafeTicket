/** Guest checkout identity helpers. */

const PAYME_PENDING_KEY = 'payme_pending_order';
const PAYME_PENDING_MS = 45 * 60 * 1000;

export function stashPaymePendingOrder(orderId) {
  try {
    const id = Number(orderId);
    if (!Number.isFinite(id) || id <= 0) return;
    sessionStorage.setItem(PAYME_PENDING_KEY, JSON.stringify({ id, ts: Date.now() }));
  } catch {
    /* ignore quota / private mode */
  }
}

export function readPaymePendingOrder(now = Date.now()) {
  try {
    const raw = sessionStorage.getItem(PAYME_PENDING_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const id = Number(parsed?.id);
    const ts = Number(parsed?.ts);
    if (!Number.isFinite(id) || id <= 0 || !Number.isFinite(ts) || now - ts > PAYME_PENDING_MS) {
      sessionStorage.removeItem(PAYME_PENDING_KEY);
      return null;
    }
    return { id, ts };
  } catch {
    return null;
  }
}

export function clearPaymePendingOrder() {
  try {
    sessionStorage.removeItem(PAYME_PENDING_KEY);
  } catch {
    /* ignore */
  }
}

/** Resume /checkout/payme/success when PayMe returns to `/` instead of the success URL. */
export function shouldRescuePaymeReturn(pathname, referrer, pending) {
  if (!pending) return false;
  const path = String(pathname || '');
  if (path.startsWith('/checkout/payme/')) return false;
  if (/payme/i.test(String(referrer || ''))) return true;
  return path === '/' || path === '';
}



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
