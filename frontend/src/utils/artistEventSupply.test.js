import { describe, expect, it } from 'vitest';
import {
  pickMostSupplyEventId,
  eventTicketCount,
  formatAvailableTicketsLabel,
} from './artistEventSupply';

describe('formatAvailableTicketsLabel', () => {
  it('labels zero inventory without a count', () => {
    expect(formatAvailableTicketsLabel(0)).toBe('אין כרטיסים זמינים');
  });

  it('uses singular Hebrew for one ticket', () => {
    expect(formatAvailableTicketsLabel(1)).toBe('🎫 כרטיס אחד זמין');
  });

  it('shows the count for multiple tickets', () => {
    expect(formatAvailableTicketsLabel(5)).toBe('🎫 5 כרטיסים זמינים');
  });
});

describe('eventTicketCount', () => {
  it('treats missing inventory as zero', () => {
    expect(eventTicketCount({})).toBe(0);
    expect(eventTicketCount({ tickets_count: null })).toBe(0);
  });
});

describe('pickMostSupplyEventId', () => {
  it('does not badge a list with no inventory', () => {
    expect(
      pickMostSupplyEventId([
        { id: 1, tickets_count: 0, date: '2026-08-20' },
        { id: 2, tickets_count: 0, date: '2026-08-21' },
      ])
    ).toBeNull();
  });
});
