/**
 * Seller dashboard sales helpers: quantity + grouping for accordion cards.
 *
 * Root cause of "1 כרטיסים" on sold multi-seat listings:
 * UI used `available_quantity || 1`, and after sale available_quantity is 0 → falsy → 1.
 */

export const SOLD_LISTING_STATUSES = ['sold', 'pending_payout', 'paid_out'];

export function listingDisplayQuantity(listing) {
  if (!listing) return 1;
  const explicit = Number(listing.quantity);
  if (Number.isFinite(explicit) && explicit > 0) return Math.trunc(explicit);

  const avail = Number(listing.available_quantity);
  // Do NOT treat 0 as missing — sold rows legitimately have available_quantity=0.
  if (Number.isFinite(avail) && avail > 0) return Math.trunc(avail);

  const members = Array.isArray(listing._memberIds) ? listing._memberIds.length : 0;
  if (members > 0) return members;

  return 1;
}

export function salesListingStatusLabel(status) {
  switch (status) {
    case 'pending_approval':
      return 'בבדיקה';
    case 'active':
      return 'פעיל';
    case 'sold':
      return 'נמכר';
    case 'pending_payout':
      return 'ממתין לתשלום';
    case 'paid_out':
      return 'שולם';
    case 'reserved':
      return 'שמור';
    case 'taken':
      return 'נתפס';
    default:
      return status || '';
  }
}

export function salesListingStatusClass(status) {
  if (!status) return 'status-unknown';
  return `status-${String(status).replace(/\s+/g, '_')}`;
}

/**
 * Collapse multi-seat sales into one accordion card:
 * - sold rows sharing order_id
 * - active rows sharing listing_group_id
 */
export function groupSellerListings(listings) {
  const map = new Map();
  const orderKeys = [];

  for (const listing of listings || []) {
    if (!listing || listing.id == null) continue;

    let key;
    if (SOLD_LISTING_STATUSES.includes(listing.status) && listing.order_id != null) {
      key = `order:${listing.order_id}`;
    } else if (listing.listing_group_id) {
      key = `group:${listing.listing_group_id}:${listing.status}`;
    } else {
      key = `ticket:${listing.id}`;
    }

    if (!map.has(key)) {
      map.set(key, {
        ...listing,
        _groupKey: key,
        _memberIds: [listing.id],
        _seatParts: [listing],
        quantity: listingDisplayQuantity(listing),
      });
      orderKeys.push(key);
      continue;
    }

    const group = map.get(key);
    group._memberIds.push(listing.id);
    group._seatParts.push(listing);
    group.quantity = Math.max(
      listingDisplayQuantity(group),
      listingDisplayQuantity(listing),
      group._memberIds.length
    );
    // Prefer richer payout / escrow fields if later members carry them.
    if (group.expected_payout == null && listing.expected_payout != null) {
      group.expected_payout = listing.expected_payout;
    }
    if (!group.escrow_payout_status && listing.escrow_payout_status) {
      group.escrow_payout_status = listing.escrow_payout_status;
      group.escrow_payout_eligible_date = listing.escrow_payout_eligible_date;
    }
  }

  return orderKeys.map((k) => map.get(k));
}

export function formatTicketsCountHe(qty) {
  const n = listingDisplayQuantity({ quantity: qty });
  return `${n} ${n === 1 ? 'כרטיס' : 'כרטיסים'}`;
}
