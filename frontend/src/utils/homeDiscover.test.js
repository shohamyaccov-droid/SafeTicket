import { describe, expect, it } from 'vitest';
import { eventHref } from './eventSeo';
import {
  filterLastMinuteEvents,
  filterHighDemandEvents,
  filterSeasonSportsEvents,
  applyHotEventPlaceholder,
  applySportEventPlaceholder,
  groupEventsByPerformer,
  HOME_DISCOVER_ROW_ORDER,
  LAST_MINUTE_WINDOW_DAYS,
  performerNavigateTarget,
} from './homeDiscover';

describe('performerNavigateTarget', () => {
  it('puts sold-out demand shows above last-minute on the homepage', () => {
    expect(HOME_DISCOVER_ROW_ORDER[0]).toBe('hot-soldout');
    expect(LAST_MINUTE_WINDOW_DAYS).toBe(14);
    expect(HOME_DISCOVER_ROW_ORDER.indexOf('hot-soldout')).toBeLessThan(
      HOME_DISCOVER_ROW_ORDER.indexOf('last-minute'),
    );
    expect(HOME_DISCOVER_ROW_ORDER.indexOf('last-minute')).toBeLessThan(
      HOME_DISCOVER_ROW_ORDER.indexOf('recommended'),
    );
    expect(HOME_DISCOVER_ROW_ORDER.indexOf('music')).toBeLessThan(
      HOME_DISCOVER_ROW_ORDER.indexOf('sports-season'),
    );
    expect(HOME_DISCOVER_ROW_ORDER.indexOf('sports-season')).toBeLessThan(
      HOME_DISCOVER_ROW_ORDER.indexOf('standup'),
    );
  });
  it('routes a single upcoming event with tickets straight to EventDetailsPage', () => {
    const event = { id: 11, slug: 'omer-adam-bloomfield', tickets_count: 4, date: '2099-08-01' };
    const target = performerNavigateTarget({
      artistId: 7,
      events: [event, { id: 12, slug: 'sold-out-date', tickets_count: 0, date: '2099-09-01' }],
    });
    expect(target).toEqual({ type: 'event', href: eventHref(event) });
  });

  it('routes multiple in-stock dates to the artist page', () => {
    const target = performerNavigateTarget({
      artistId: 7,
      artistSlug: 'eyal-golan',
      events: [
        { id: 11, slug: 'date-a', tickets_count: 2, date: '2099-08-01' },
        { id: 12, slug: 'date-b', tickets_count: 1, date: '2099-09-01' },
      ],
    });
    expect(target).toEqual({ type: 'artist', href: '/artist/eyal-golan' });
  });

  it('groups homepage events and still prefers a single in-stock date', () => {
    const groups = groupEventsByPerformer([
      {
        id: 1,
        slug: 'only-date',
        artist: 9,
        artist_detail: { id: 9, name: 'אמן' },
        tickets_count: 3,
        date: '2099-10-01',
        name: 'הופעה',
      },
    ]);
    expect(performerNavigateTarget(groups[0])).toEqual({
      type: 'event',
      href: '/event/only-date',
    });
  });
});

describe('filterLastMinuteEvents', () => {
  const todayStart = new Date('2026-08-27T00:00:00');

  it('keeps upcoming events within 14 days, soonest first, and drops past or far-future', () => {
    const past = { id: 1, date: '2026-08-26T20:00:00', tickets_count: 2 };
    const soon = { id: 2, date: '2026-08-29T20:00:00', tickets_count: 1 };
    const later = { id: 3, date: '2026-09-08T20:00:00', tickets_count: 4 };
    const tooFar = { id: 4, date: '2026-09-12T20:00:00', tickets_count: 3 };
    const noTickets = { id: 5, date: '2026-08-30T20:00:00', tickets_count: 0 };

    const result = filterLastMinuteEvents([later, tooFar, past, soon, noTickets], todayStart);
    expect(result.map((ev) => ev.id)).toEqual([2, 3]);
  });
});

describe('filterHighDemandEvents', () => {
  it('keeps only high_demand events, soonest first', () => {
    const hotLater = { id: 2, date: '2026-10-01T21:00:00', high_demand: true };
    const skip = { id: 3, date: '2026-09-16T21:00:00', high_demand: false };
    const hotSoon = { id: 1, date: '2026-09-16T20:00:00', high_demand: true };
    expect(filterHighDemandEvents([hotLater, skip, hotSoon]).map((ev) => ev.id)).toEqual([1, 2]);
  });

  it('applies a placeholder image when the catalog has none', () => {
    const ev = applyHotEventPlaceholder({
      id: 9,
      artist_name: 'שרית חדד',
      high_demand: true,
    });
    expect(ev.image_url).toMatch(/^https:\/\/images\.unsplash\.com\//);
  });
});

describe('filterSeasonSportsEvents', () => {
  it('keeps only hot football and basketball events, soonest first', () => {
    const football = {
      id: 1,
      date: '2026-09-14T20:30:00',
      category: 'football',
      high_demand: true,
    };
    const basketball = {
      id: 2,
      date: '2026-11-12T21:05:00',
      category: 'basketball',
      is_hot: true,
    };
    const concert = {
      id: 3,
      date: '2026-09-16T21:00:00',
      category: 'concert',
      high_demand: true,
    };
    const coldFootball = {
      id: 4,
      date: '2026-10-01T20:30:00',
      category: 'football',
      high_demand: false,
    };
    expect(filterSeasonSportsEvents([basketball, concert, coldFootball, football]).map((ev) => ev.id)).toEqual([
      1, 2,
    ]);
  });

  it('applies a stadium placeholder when the catalog has none', () => {
    const ev = applySportEventPlaceholder({
      id: 9,
      category: 'football',
      high_demand: true,
    });
    expect(ev.image_url).toMatch(/^https:\/\/images\.unsplash\.com\//);
  });
});
