import { describe, expect, it } from 'vitest';
import { buildClientEventJsonLd, buildTicketOfferJsonLd } from './eventJsonLdClient';

describe('buildClientEventJsonLd', () => {
  it('emits Event + AggregateOffer with name, date, venue, price, and stock', () => {
    const data = buildClientEventJsonLd(
      {
        name: 'אייל גולן',
        slug: 'eyal-golan-2026-08-29',
        date: '2026-08-29T20:00:00+03:00',
        venue: 'בלומפילד',
        city: 'תל אביב',
        country: 'IL',
      },
      [
        { asking_price: 250 },
        { listing_price: 400 },
      ],
    );
    expect(data['@type']).toBe('Event');
    expect(data.name).toBe('אייל גולן');
    expect(data.startDate).toBe('2026-08-29T20:00:00+03:00');
    expect(data.location.name).toBe('בלומפילד');
    expect(data.offers['@type']).toBe('AggregateOffer');
    expect(data.offers.lowPrice).toBe('250.00');
    expect(data.offers.highPrice).toBe('400.00');
    expect(data.offers.availability).toContain('InStock');
  });

  it('marks sold-out events when no listings exist', () => {
    const data = buildClientEventJsonLd({ name: 'Show', date: '2026-09-01', venue: 'Hall' }, []);
    expect(data.offers['@type']).toBe('Offer');
    expect(data.offers.availability).toContain('SoldOut');
  });
});

describe('buildTicketOfferJsonLd', () => {
  it('wraps a listing in Event + Offer', () => {
    const data = buildTicketOfferJsonLd({
      id: 9,
      event_name: 'QA Concert',
      event_date: '2026-08-20T19:00:00Z',
      venue: 'Menora',
      asking_price: '120.00',
      available_quantity: 2,
    });
    expect(data['@type']).toBe('Event');
    expect(data.offers['@type']).toBe('Offer');
    expect(data.offers.price).toBe('120.00');
    expect(data.offers.availability).toContain('InStock');
  });
});
