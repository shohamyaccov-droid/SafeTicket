import { describe, expect, it } from 'vitest';
import {
  filterMarketplaceTickets,
  isListingGroupTaken,
  isTicketTaken,
} from './ticketAvailability';

describe('ticketAvailability', () => {
  it('detects permanently taken tickets', () => {
    expect(isTicketTaken({ status: 'taken' })).toBe(true);
    expect(isTicketTaken({ status: 'active' })).toBe(false);
    expect(isTicketTaken({ status: 'reserved' })).toBe(false);
  });

  it('keeps taken tickets in marketplace filter and drops sold', () => {
    const rows = filterMarketplaceTickets([
      { id: 1, status: 'active', available_quantity: 2 },
      { id: 2, status: 'taken', available_quantity: 1 },
      { id: 3, status: 'sold', available_quantity: 0 },
      { id: 4, status: 'active', available_quantity: 0 },
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
});
