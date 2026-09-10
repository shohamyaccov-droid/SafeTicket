/**
 * Ticket marketplace availability helpers.
 * `taken` = permanent lock (נתפס); distinct from temporary cart `reserved`.
 */

import {
  isListingGroupCartLocked,
  isTicketCartLocked,
  listingGroupCartLockedUntilMs,
} from './ticketLock';

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
export function pickBuyableListingTicket(group) {
  const tickets = Array.isArray(group?.tickets) ? group.tickets : group ? [group] : [];
  const active = tickets.find(
    (t) =>
      t &&
      t.status === 'active' &&
      !isTicketTaken(t) &&
      (t.available_quantity == null || Number(t.available_quantity) > 0),
  );
  if (active) return active;
  return tickets.find((t) => t && t.status === 'reserved' && !isTicketTaken(t)) || null;
}

export function isListingGroupTaken(group) {
  if (!group) return false;
  if (group.is_taken === true && !(group.available_count > 0)) return true;
  const tickets = Array.isArray(group.tickets) ? group.tickets : [];
  if (tickets.length === 0) return false;
  return tickets.every((t) => isTicketTaken(t));
}

/** Keep marketplace rows that are buyable, in a cart hold, permanently taken, or sold. */
export function filterMarketplaceTickets(raw) {
  const list = Array.isArray(raw) ? raw : [];
  return list.filter((t) => {
    if (!t) return false;
    if (isTicketTaken(t) || t.is_taken === true) return true;
    if (t.status === 'sold' || t.status === 'pending_payout') return true;
    if (t.status === 'reserved' || t.is_locked === true) return true;
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
  if (isListingGroupCartLocked(group)) return true;
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

/** Unit asking price for a listing group (ILS), or Infinity if missing. */
export function listingGroupUnitPrice(group) {
  const raw =
    group?.price ??
    group?.tickets?.[0]?.asking_price ??
    group?.tickets?.[0]?.original_price;
  const n = parseFloat(raw);
  return Number.isFinite(n) ? n : Infinity;
}

/**
 * Cheapest buyable listing in the visible set (skips taken / own / empty).
 * Used by the mobile sticky buy bar to open the best-priced ticket.
 */
export function pickCheapestBuyableGroup(groups, user) {
  let best = null;
  let bestPrice = Infinity;
  for (const group of groups || []) {
    if (!group || isListingUnavailableForBuyer(group, user)) continue;
    if (!(Number(group.available_count) > 0)) continue;
    const price = listingGroupUnitPrice(group);
    if (price < bestPrice) {
      best = group;
      bestPrice = price;
    }
  }
  return best;
}

function normalizeSeatPart(value) {
  if (value == null || value === '') return '';
  if (typeof value === 'object') {
    const nested = value.id ?? value.pk ?? value.name ?? value.label;
    return String(nested ?? '').trim().toLowerCase();
  }
  return String(value).trim().toLowerCase();
}

/** Block / section identity for marketplace grouping. */
export function ticketVenueSectionKey(ticket) {
  if (!ticket) return '';
  const fromVenue = normalizeSeatPart(ticket.venue_section);
  if (fromVenue) return fromVenue;
  return normalizeSeatPart(ticket.section || ticket.custom_section_text || ticket.section_legacy);
}

/** Row identity for marketplace grouping. */
export function ticketRowKey(ticket) {
  if (!ticket) return '';
  return normalizeSeatPart(ticket.row ?? ticket.row_number ?? ticket.seat_row);
}

/**
 * Marketplace card identity. Tickets share a card only when they belong to the
 * same listing (or seller+price fallback) AND the same venue section AND row.
 */
export function listingMarketplaceGroupKey(ticket) {
  const section = ticketVenueSectionKey(ticket);
  const row = ticketRowKey(ticket);
  const seatKey = `${section}::${row}`;
  const listingGroupId = ticket?.listing_group_id;
  if (listingGroupId !== null && listingGroupId !== undefined && listingGroupId !== '') {
    return `${String(listingGroupId).trim()}::${seatKey}`;
  }
  const sellerId =
    ticket?.seller_username || ticket?.seller_id || ticket?.seller || 'unknown';
  const sellerKey =
    typeof sellerId === 'object' ? String(sellerId.id ?? sellerId.pk ?? 'unknown') : String(sellerId);
  const price = ticket?.asking_price ?? ticket?.original_price ?? '';
  return `${sellerKey}_${price}::${seatKey}`;
}

/** Stable UI id for a grouped listing row. */
export function stableListingGroupKey(group) {
  if (!group) return '';
  if (group.id != null && group.id !== '') return String(group.id);
  const lid = group.listing_group_id;
  if (lid != null && lid !== '') return String(lid).trim();
  return '';
}

/**
 * Group marketplace tickets into selectable cards.
 * Same block + different rows always become separate cards.
 */
export function groupTicketsByListing(ticketsArray) {
  const groups = {};
  const list = Array.isArray(ticketsArray) ? ticketsArray : [];

  list.forEach((ticket) => {
    if (!ticket) return;
    const groupKey = listingMarketplaceGroupKey(ticket);
    const listingGroupId = ticket.listing_group_id;

    if (!groups[groupKey]) {
      groups[groupKey] = {
        id: groupKey,
        tickets: [],
        price: ticket.asking_price || ticket.original_price,
        available_count: 0,
        seller_id:
          ticket.seller_id ??
          (typeof ticket.seller === 'object' && ticket.seller != null
            ? ticket.seller.id
            : ticket.seller),
        seller_username: ticket.seller_username,
        seller_is_verified: ticket.seller_is_verified || false,
        delivery_method: ticket.delivery_method || 'instant',
        listing_group_id: listingGroupId,
      };
    }

    groups[groupKey].tickets.push(ticket);
    if (
      ticket.status === 'active'
      || (ticket.status === 'reserved' && !isTicketCartLocked(ticket))
    ) {
      groups[groupKey].available_count += 1;
    }
  });

  return Object.values(groups).map((g) => {
    const lockMs = listingGroupCartLockedUntilMs(g);
    const buyableFirst = [];
    const rest = [];
    for (const t of g.tickets) {
      if (t && t.status === 'active' && !isTicketTaken(t)) buyableFirst.push(t);
      else rest.push(t);
    }
    return {
      ...g,
      tickets: [...buyableFirst, ...rest],
      is_taken: isListingGroupTaken(g),
      is_cart_locked: isListingGroupCartLocked(g),
      locked_until: lockMs != null ? new Date(lockMs).toISOString() : null,
    };
  });
}
