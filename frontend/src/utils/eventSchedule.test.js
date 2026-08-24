import { describe, expect, it } from 'vitest';
import {
  eventArtistId,
  isEventDatePassed,
  pickNextUpcomingEvent,
} from './eventSchedule';

describe('eventSchedule', () => {
  const now = new Date('2026-08-25T12:00:00Z');

  it('detects past event dates', () => {
    expect(isEventDatePassed('2026-08-24T18:00:00Z', now)).toBe(true);
    expect(isEventDatePassed('2026-08-26T18:00:00Z', now)).toBe(false);
  });

  it('picks the next in-stock future date for an artist', () => {
    const next = pickNextUpcomingEvent(
      [
        { id: 1, date: '2026-08-20T18:00:00Z', tickets_count: 4 },
        { id: 2, date: '2026-08-28T18:00:00Z', tickets_count: 0 },
        { id: 3, date: '2026-09-01T18:00:00Z', tickets_count: 2 },
      ],
      { now, excludeId: 1 }
    );
    expect(next.id).toBe(3);
  });

  it('reads artist id from nested artist objects', () => {
    expect(eventArtistId({ artist: { id: 44, name: 'x' } })).toBe(44);
  });
});
