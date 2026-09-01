/**
 * Temporary cart holds (someone is in checkout) vs permanent נתפס.
 */

/** Stage 1: details form after Buy Now. Keep in sync with backend CART_HOLD_MINUTES. */
export const CART_HOLD_SECONDS = 2 * 60;
/** Stage 2: after Order exists / PayMe tab. Keep in sync with backend PAYMENT_HOLD_MINUTES. */
export const PAYMENT_HOLD_SECONDS = 10 * 60;

export function ticketLockUntilMs(ticket) {
  if (!ticket) return null;
  const raw = ticket.locked_until;
  if (raw == null || raw === '') return null;
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : null;
}

export function remainingSecondsUntil(iso, nowMs = Date.now()) {
  if (iso == null || iso === '') return null;
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return null;
  return Math.max(0, Math.floor((ms - nowMs) / 1000));
}

export function isTicketCartLocked(ticket, nowMs = Date.now()) {
  if (!ticket) return false;
  const until = ticketLockUntilMs(ticket);
  if (until != null) {
    return until > nowMs;
  }
  if (ticket.is_locked === true) return true;
  return false;
}

export function formatLockCountdown(remainingMs) {
  const total = Math.max(0, Math.ceil(Number(remainingMs) / 1000) || 0);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export function cartLockLabel(remainingMs) {
  return `מישהו בתהליך קנייה. משתחרר בעוד ${formatLockCountdown(remainingMs)}`;
}

/** Earliest lock expiry among currently locked seats, or null. */
export function listingGroupCartLockedUntilMs(group, nowMs = Date.now()) {
  const tickets = Array.isArray(group?.tickets) ? group.tickets : [];
  let earliest = null;
  for (const t of tickets) {
    if (!isTicketCartLocked(t, nowMs)) continue;
    const until = ticketLockUntilMs(t);
    if (until == null) continue;
    if (earliest == null || until < earliest) earliest = until;
  }
  return earliest;
}

/**
 * True when every remaining seat is in someone else's cart hold
 * (no active/buyable seat left).
 */
export function isListingGroupCartLocked(group, nowMs = Date.now()) {
  const tickets = Array.isArray(group?.tickets) ? group.tickets : [];
  if (tickets.length === 0) {
    const until = group?.locked_until ? Date.parse(group.locked_until) : null;
    if (group?.is_cart_locked === true && until != null) return until > nowMs;
    return Boolean(group?.is_cart_locked);
  }
  const buyable = tickets.filter(
    (t) => t && t.status !== 'taken' && t.status !== 'sold' && t.status !== 'pending_payout'
      && t.is_taken !== true
      && !isTicketCartLocked(t, nowMs),
  );
  return buyable.length === 0 && tickets.some((t) => isTicketCartLocked(t, nowMs));
}
