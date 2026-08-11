/**
 * Ticket marketplace availability helpers.
 * `taken` = permanent lock (נתפס); distinct from temporary cart `reserved`.
 */

export const TICKET_STATUS_TAKEN = 'taken';

export function isTicketTaken(ticket) {
  if (!ticket) return false;
  if (ticket.is_taken === true) return true;
  return (
    ticket.status === TICKET_STATUS_TAKEN ||
    ticket.status === 'sold' ||
    ticket.status === 'pending_payout'
  );
}

/**
 * A listing group is "taken" when every ticket in it is permanently taken/sold,
 * or when the group was flagged `is_taken` with no purchasable seats.
 */
export function isListingGroupTaken(group) {
  if (!group) return false;
  if (group.is_taken === true && !(group.available_count > 0)) return true;
  const tickets = Array.isArray(group.tickets) ? group.tickets : [];
  if (tickets.length === 0) return false;
  return tickets.every((t) => isTicketTaken(t));
}

/** Keep marketplace rows that are buyable, permanently taken, or sold (נתפס UI). */
export function filterMarketplaceTickets(raw) {
  const list = Array.isArray(raw) ? raw : [];
  return list.filter((t) => {
    if (!t) return false;
    if (isTicketTaken(t) || t.is_taken === true) return true;
    if (t.status === 'sold' || t.status === 'pending_payout') return true;
    return Number(t.available_quantity) > 0;
  });
}

/**
 * True when the listing belongs to the logged-in user (cannot buy own tickets).
 * Mirrors EventDetailsPage seller matching (id / nested seller / username).
 */
export function isCurrentUserOwnListing(user, ticket, group) {
  if (!user || !ticket) return false;
  const uid = Number(user.id);
  const sidRaw = ticket.seller_id ?? ticket.seller;
  const sid =
    sidRaw != null && typeof sidRaw === 'object'
      ? Number(sidRaw.id)
      : Number(sidRaw);
  if (!Number.isNaN(sid) && sid === uid) return true;
  if (ticket.seller_username && user.username && ticket.seller_username === user.username) {
    return true;
  }
  const gid = group?.seller_id ?? group?.seller;
  const gsid =
    gid != null && typeof gid === 'object' ? Number(gid.id) : Number(gid);
  if (!Number.isNaN(gsid) && gsid === uid) return true;
  if (group?.seller_username && user.username && group.seller_username === user.username) {
    return true;
  }
  return false;
}

/** True when the buyer cannot purchase this listing (taken or own). */
export function isListingUnavailableForBuyer(group, user) {
  if (!group) return true;
  if (isListingGroupTaken(group)) return true;
  const first = Array.isArray(group.tickets) ? group.tickets[0] : null;
  return isCurrentUserOwnListing(user, first, group);
}

/**
 * Sort rank for marketplace rows: 0 = buyable (top), 1 = taken/own (bottom).
 */
export function listingBuyerAvailabilityRank(group, user) {
  return isListingUnavailableForBuyer(group, user) ? 1 : 0;
}

/**
 * Apply a primary comparator, then push taken/own listings to the bottom
 * (stable within each tier when the engine preserves sort stability).
 */
export function sortListingGroupsForBuyer(groups, user, primaryCompare) {
  const list = Array.isArray(groups) ? [...groups] : [];
  if (typeof primaryCompare === 'function') {
    list.sort(primaryCompare);
  }
  list.sort(
    (a, b) => listingBuyerAvailabilityRank(a, user) - listingBuyerAvailabilityRank(b, user)
  );
  return list;
}
