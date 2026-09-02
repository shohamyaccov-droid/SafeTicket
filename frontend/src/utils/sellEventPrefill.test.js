import { describe, expect, it } from 'vitest';
import { parseSellPresetEventId, sellCategoryFromEvent, artistIdFromEvent, waitlistDemandCount, sellerWaitlistCtaLabel, sellTicketsPathForEvent } from './sellEventPrefill';

describe('sellEventPrefill', () => {
  it('parses event query params', () => {
    expect(parseSellPresetEventId('?event=42')).toBe('42');
    expect(parseSellPresetEventId('event_id=7')).toBe('7');
    expect(parseSellPresetEventId('')).toBe('');
  });

  it('builds a sell deep link and hides empty waitlist demand', () => {
    expect(sellTicketsPathForEvent({ id: 12 })).toBe('/sell/new?event=12');
    expect(waitlistDemandCount({ waitlist_count: 0 })).toBe(0);
    expect(waitlistDemandCount({ waitlist_count: undefined })).toBe(0);
    expect(waitlistDemandCount({ waitlist_count: 4 })).toBe(4);
    expect(sellerWaitlistCtaLabel(4)).toContain('4 אנשים מחכים');
  });

  it('maps event category and artist for the sell wizard', () => {
    expect(sellCategoryFromEvent({ category: 'football' })).toBe('sport');
    expect(sellCategoryFromEvent({ category: 'concert' })).toBe('concert');
    expect(artistIdFromEvent({ artist: { id: 9 } })).toBe('9');
    expect(artistIdFromEvent({ artist_detail: { id: 3 } })).toBe('3');
  });
});
