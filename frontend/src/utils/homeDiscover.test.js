import { describe, expect, it } from 'vitest';
import { eventHref } from './eventSeo';
import {
  filterLastMinuteEvents,
  filterSeasonSportsEvents,
  applySportEventPlaceholder,
  groupEventsByPerformer,
  HOME_DISCOVER_ROW_ORDER,
  LAST_MINUTE_WINDOW_DAYS,
  performerNavigateTarget,
} from './homeDiscover';

describe('performerNavigateTarget', () => {
  it('puts last-minute first, with sports season below concerts', () => {
    expect(HOME_DISCOVER_ROW_ORDER[0]).toBe('last-minute');
    expect(LAST_MINUTE_WINDOW_DAYS).toBe(14);
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

  it('splits NEXT homepage cards by venue and routes into that location only', () => {
    const ramat = {
      id: 1,
      slug: 'next-rg-8',
      name: 'NEXT 2026 - אצטדיון ר"ג (8.10)',
      venue: 'אצטדיון ר"ג',
      city: 'רמת גן',
      artist: 99,
      artist_detail: { id: 99, name: 'NEXT', slug: 'next' },
      tickets_count: 2,
      date: '2026-10-08T17:00:00Z',
    };
    const jerusalem = {
      id: 2,
      slug: 'next-jr-3',
      name: 'NEXT 2026 - פיס ארנה י-ם (3.12)',
      venue: 'פיס ארנה י-ם',
      city: 'ירושלים',
      artist: 99,
      artist_detail: { id: 99, name: 'NEXT', slug: 'next' },
      tickets_count: 3,
      date: '2026-12-03T18:00:00Z',
    };
    const ramatB = {
      ...ramat,
      id: 3,
      slug: 'next-rg-10',
      name: 'NEXT 2026 - אצטדיון ר"ג (10.10)',
      tickets_count: 1,
      date: '2026-10-10T17:00:00Z',
    };
    const groups = groupEventsByPerformer([ramat, jerusalem, ramatB]);
    expect(groups).toHaveLength(2);
    const names = groups.map((g) => g.performerName).sort();
    expect(names).toEqual(['NEXT - אצטדיון רמת גן', 'NEXT - פיס ארנה ירושלים']);
    const rg = groups.find((g) => g.performerName.includes('רמת גן'));
    expect(rg.events.map((e) => e.id).sort()).toEqual([1, 3]);
    expect(performerNavigateTarget(rg)).toEqual({ type: 'event', href: eventHref(ramat) });
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

  it('applies a club-crest placeholder when the catalog has none', () => {
    const ev = applySportEventPlaceholder({
      id: 9,
      category: 'football',
      high_demand: true,
      artist_name: 'מכבי חיפה',
    });
    expect(ev.image_url).toMatch(/^https:\/\/upload\.wikimedia\.org\//);
    expect(ev.image_url).toContain('%D7%9E%D7%9B%D7%91%D7%99_%D7%97%D7%99%D7%A4%D7%94');
  });
});
