/**
 * Ticket marketplace availability helpers.
 * `taken` = permanent lock (נתפס); distinct from temporary cart `reserved`.
 */

export const TICKET_STATUS_TAKEN = 'taken';

export function isTicketTaken(ticket) {
  return ticket != null && ticket.status === TICKET_STATUS_TAKEN;
}

/**
 * A listing group is "taken" when every ticket in it is permanently taken,
 * or when the group was flagged `is_taken` with no purchasable seats.
 */
export function isListingGroupTaken(group) {
  if (!group) return false;
  if (group.is_taken === true && !(group.available_count > 0)) return true;
  const tickets = Array.isArray(group.tickets) ? group.tickets : [];
  if (tickets.length === 0) return false;
  return tickets.every((t) => isTicketTaken(t));
}

/** Keep marketplace rows that are buyable or permanently taken (for נתפס UI). */
export function filterMarketplaceTickets(raw) {
  const list = Array.isArray(raw) ? raw : [];
  return list.filter((t) => {
    if (!t) return false;
    if (isTicketTaken(t)) return true;
    if (t.status === 'sold' || t.status === 'pending_payout') return false;
    return Number(t.available_quantity) > 0;
  });
}
