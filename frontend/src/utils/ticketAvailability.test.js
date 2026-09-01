import { describe, expect, it } from 'vitest';
import {
  filterMarketplaceTickets,
  isListingGroupTaken,
  isListingUnavailableForBuyer,
  isTicketTaken,
  listingGroupUnitPrice,
  pickCheapestBuyableGroup,
  pickBuyableListingTicket,
  sortListingGroupsForBuyer,
} from './ticketAvailability';

describe('ticketAvailability', () => {
  it('detects permanently taken tickets', () => {
    expect(isTicketTaken({ status: 'taken' })).toBe(true);
    expect(isTicketTaken({ status: 'sold' })).toBe(true);
    expect(isTicketTaken({ is_taken: true, status: 'active' })).toBe(true);
    expect(isTicketTaken({ status: 'active' })).toBe(false);
    expect(isTicketTaken({ status: 'reserved' })).toBe(false);
  });

  it('keeps taken and sold tickets in marketplace filter', () => {
    const rows = filterMarketplaceTickets([
      { id: 1, status: 'active', available_quantity: 2 },
      { id: 2, status: 'taken', available_quantity: 1 },
      { id: 3, status: 'sold', available_quantity: 0 },
      { id: 4, status: 'active', available_quantity: 0 },
    ]);
    expect(rows.map((t) => t.id)).toEqual([1, 2, 3]);
  });

  it('keeps reserved cart-hold tickets in the marketplace list', () => {
    const rows = filterMarketplaceTickets([
      { id: 1, status: 'active', available_quantity: 1 },
      { id: 2, status: 'reserved', is_locked: true, available_quantity: 1 },
      { id: 3, status: 'inactive', available_quantity: 0 },
    ]);
    expect(rows.map((t) => t.id)).toEqual([1, 2]);
  });

  it('marks a listing group as taken when every seat is taken', () => {
    const group = {
      available_count: 0,
      tickets: [
        { id: 1, status: 'taken' },
        { id: 2, status: 'taken' },
      ],
    };
    expect(isListingGroupTaken(group)).toBe(true);
  });

  it('does not mark a group taken when any seat is still active', () => {
    const group = {
      available_count: 1,
      tickets: [
        { id: 1, status: 'taken' },
        { id: 2, status: 'active' },
      ],
    };
    expect(isListingGroupTaken(group)).toBe(false);
  });

  it('pushes taken and own listings below buyable ones while keeping price order', () => {
    const user = { id: 9, username: 'me' };
    const groups = [
      {
        id: 'taken',
        price: 10,
        available_count: 0,
        tickets: [{ id: 1, status: 'taken', seller_id: 1 }],
      },
      {
        id: 'cheap',
        price: 50,
        available_count: 2,
        tickets: [{ id: 2, status: 'active', seller_id: 1 }],
      },
      {
        id: 'own',
        price: 20,
        available_count: 1,
        tickets: [{ id: 3, status: 'active', seller_id: 9 }],
      },
      {
        id: 'pricey',
        price: 100,
        available_count: 1,
        tickets: [{ id: 4, status: 'active', seller_id: 2 }],
      },
    ];
    const sorted = sortListingGroupsForBuyer(groups, user, (a, b) =>
      parseFloat(a.price) - parseFloat(b.price)
    );
    expect(sorted.map((g) => g.id)).toEqual(['cheap', 'pricey', 'taken', 'own']);
    expect(isListingUnavailableForBuyer(sorted[2], user)).toBe(true);
    expect(isListingUnavailableForBuyer(sorted[3], user)).toBe(true);
  });

  it('picks the cheapest buyable listing and skips taken/own', () => {
    const user = { id: 9, username: 'me' };
    const groups = [
      {
        id: 'taken',
        price: 10,
        available_count: 0,
        tickets: [{ id: 1, status: 'taken', seller_id: 1 }],
      },
      {
        id: 'own',
        price: 15,
        available_count: 2,
        tickets: [{ id: 2, status: 'active', seller_id: 9 }],
      },
      {
        id: 'mid',
        price: 80,
        available_count: 1,
        tickets: [{ id: 3, status: 'active', seller_id: 1 }],
      },
      {
        id: 'cheap',
        price: 40,
        available_count: 2,
        tickets: [{ id: 4, status: 'active', seller_id: 2 }],
      },
    ];
    expect(pickCheapestBuyableGroup(groups, user)?.id).toBe('cheap');
    expect(listingGroupUnitPrice(groups[3])).toBe(40);
    expect(pickCheapestBuyableGroup([], user)).toBeNull();
  });

  it('picks an active remaining seat when earlier seats in the listing were sold', () => {
    const group = {
      available_count: 2,
      tickets: [
        { id: 1, status: 'sold', available_quantity: 0 },
        { id: 2, status: 'sold', available_quantity: 0 },
        { id: 3, status: 'active', available_quantity: 1 },
        { id: 4, status: 'active', available_quantity: 1 },
      ],
    };
    expect(isListingGroupTaken(group)).toBe(false);
    expect(pickBuyableListingTicket(group)?.id).toBe(3);
  });
});
