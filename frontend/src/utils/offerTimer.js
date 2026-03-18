/**
 * Offer timer utilities - Phase 1: Negotiation UX
 * Timer: HH:MM (no seconds), 24h from offer creation/expires_at
 * Expired: show 'פג תוקף'
 */

/**
 * Format offer expiration time remaining as HH:MM (no seconds)
 * @param {string|Date} expiresAt - ISO string or Date
 * @returns {{ display: string, isExpired: boolean, remainingMs: number }}
 */
export const getOfferExpirationDisplay = (expiresAt) => {
  if (!expiresAt) return { display: 'פג תוקף', isExpired: true, remainingMs: 0 };
  const expires = new Date(expiresAt).getTime();
  const now = Date.now();
  const remainingMs = Math.max(0, expires - now);
  if (remainingMs <= 0) return { display: 'פג תוקף', isExpired: true, remainingMs: 0 };
  const totalMinutes = Math.floor(remainingMs / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  const display = `נותרו ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')} שעות`;
  return { display, isExpired: false, remainingMs };
};

/**
 * Calculate counter-off responses left for this negotiation (max 2 total)
 * roundCount 0 -> 2 left, roundCount 1 -> 1 left, roundCount 2 -> 0 left
 */
export const getResponsesLeft = (roundCount) => {
  const r = roundCount ?? 0;
  return Math.max(0, 2 - r);
};
