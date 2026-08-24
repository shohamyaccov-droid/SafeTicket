import { describe, expect, it } from 'vitest';
import { eventHref } from './eventSeo';
import { groupEventsByPerformer, performerNavigateTarget } from './homeDiscover';

describe('performerNavigateTarget', () => {
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
      events: [
        { id: 11, slug: 'date-a', tickets_count: 2, date: '2099-08-01' },
        { id: 12, slug: 'date-b', tickets_count: 1, date: '2099-09-01' },
      ],
    });
    expect(target).toEqual({ type: 'artist', href: '/artist/7' });
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
