import { describe, expect, it } from 'vitest';
import {
  formatTicketsCountHe,
  groupSellerListings,
  listingDisplayQuantity,
  salesListingStatusLabel,
} from './sellerSalesListings';

describe('listingDisplayQuantity', () => {
  it('uses quantity for sold rows even when available_quantity is 0', () => {
    expect(
      listingDisplayQuantity({
        status: 'sold',
        available_quantity: 0,
        quantity: 2,
      })
    ).toBe(2);
  });

  it('does not fall back to 1 when available_quantity is 0 and quantity missing', () => {
    // Without quantity, we still need a positive display; member count wins when grouped.
    expect(listingDisplayQuantity({ available_quantity: 0, _memberIds: [1, 2] })).toBe(2);
  });

  it('uses available_quantity for active inventory', () => {
    expect(listingDisplayQuantity({ status: 'active', available_quantity: 3 })).toBe(3);
  });
});

describe('groupSellerListings', () => {
  it('merges sold tickets that share an order_id and keeps order quantity', () => {
    const grouped = groupSellerListings([
      {
        id: 10,
        status: 'sold',
        order_id: 99,
        available_quantity: 0,
        quantity: 2,
        expected_payout: 598,
        asking_price: 299,
      },
      {
        id: 11,
        status: 'sold',
        order_id: 99,
        available_quantity: 0,
        quantity: 2,
        expected_payout: 598,
        asking_price: 299,
      },
    ]);
    expect(grouped).toHaveLength(1);
    expect(grouped[0].quantity).toBe(2);
    expect(grouped[0]._memberIds).toEqual([10, 11]);
    expect(formatTicketsCountHe(grouped[0].quantity)).toBe('2 כרטיסים');
  });

  it('merges active tickets in the same listing_group_id', () => {
    const grouped = groupSellerListings([
      { id: 1, status: 'active', listing_group_id: 'g1', available_quantity: 1, quantity: 1 },
      { id: 2, status: 'active', listing_group_id: 'g1', available_quantity: 1, quantity: 1 },
    ]);
    expect(grouped).toHaveLength(1);
    expect(grouped[0].quantity).toBe(2);
  });
});

describe('salesListingStatusLabel', () => {
  it('maps known statuses to Hebrew labels', () => {
    expect(salesListingStatusLabel('sold')).toBe('נמכר');
    expect(salesListingStatusLabel('active')).toBe('פעיל');
    expect(salesListingStatusLabel('pending_payout')).toBe('ממתין לתשלום');
    expect(salesListingStatusLabel('pending_approval')).toBe('בבדיקה');
  });
});
