import { describe, expect, it } from 'vitest';
import {
  cartLockLabel,
  formatLockCountdown,
  isListingGroupCartLocked,
  isTicketCartLocked,
  listingGroupCartLockedUntilMs,
} from './ticketLock';

describe('ticketLock', () => {
  const now = Date.parse('2026-09-01T12:00:00.000Z');

  it('formats MM:SS countdown copy', () => {
    expect(formatLockCountdown(125000)).toBe('02:05');
    expect(formatLockCountdown(0)).toBe('00:00');
    expect(cartLockLabel(61000)).toBe('מישהו בתהליך קנייה. משתחרר בעוד 01:01');
  });

  it('treats a future locked_until as a live cart hold', () => {
    const ticket = {
      status: 'reserved',
      is_locked: true,
      locked_until: '2026-09-01T12:05:00.000Z',
    };
    expect(isTicketCartLocked(ticket, now)).toBe(true);
    expect(isTicketCartLocked({ ...ticket, locked_until: '2026-09-01T11:59:00.000Z' }, now)).toBe(false);
  });

  it('locks a listing group only when every remaining seat is in someone else\'s cart', () => {
    const lockedUntil = '2026-09-01T12:08:00.000Z';
    const lockedGroup = {
      locked_until: lockedUntil,
      tickets: [
        { id: 1, status: 'reserved', is_locked: true, locked_until: lockedUntil },
        { id: 2, status: 'reserved', is_locked: true, locked_until: lockedUntil },
      ],
    };
    expect(isListingGroupCartLocked(lockedGroup, now)).toBe(true);
    expect(listingGroupCartLockedUntilMs(lockedGroup, now)).toBe(Date.parse(lockedUntil));

    const mixed = {
      tickets: [
        { id: 1, status: 'reserved', is_locked: true, locked_until: lockedUntil },
        { id: 2, status: 'active', is_locked: false, locked_until: null },
      ],
    };
    expect(isListingGroupCartLocked(mixed, now)).toBe(false);
  });
});
