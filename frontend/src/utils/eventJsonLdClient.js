import { eventCanonicalPath } from './eventSeo';
import { toPublicAbsoluteUrl } from './publicSite';

function numericPrice(value) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function ticketPrice(ticket) {
  if (!ticket || typeof ticket !== 'object') return null;
  return (
    numericPrice(ticket.listing_price) ??
    numericPrice(ticket.asking_price) ??
    numericPrice(ticket.price) ??
    numericPrice(ticket.unit_price)
  );
}

function venueName(event) {
  return (
    String(event?.venue || '').trim() ||
    String(event?.venue_detail?.name || '').trim() ||
    String(event?.city || '').trim() ||
    'Israel'
  );
}

/**
 * Client-side Event + Offer/AggregateOffer fallback when the API omits json_ld.
 * Google AI Overviews extract name, date, location, availability, and price.
 */
export function buildClientEventJsonLd(event, tickets = []) {
  if (!event || typeof event !== 'object') return null;
  const name = String(event.name || event.event_name || '').trim();
  if (!name) return null;

  const listing = Array.isArray(tickets) ? tickets : [];
  const prices = listing.map(ticketPrice).filter((n) => n != null);
  const offerCount = listing.length || prices.length;
  const currency = String(event.currency || event.price_currency || 'ILS').trim() || 'ILS';
  const url = toPublicAbsoluteUrl(event.canonical_url || eventCanonicalPath(event));
  const city = String(event.city || '').trim() || venueName(event);
  const availability =
    offerCount > 0 && event.status !== 'סולד אאוט'
      ? 'https://schema.org/InStock'
      : 'https://schema.org/SoldOut';

  let offers;
  if (prices.length > 0) {
    const low = Math.min(...prices);
    const high = Math.max(...prices);
    offers = {
      '@type': prices.length === 1 ? 'Offer' : 'AggregateOffer',
      url,
      priceCurrency: currency,
      availability,
    };
    if (prices.length === 1) {
      offers.price = low.toFixed(2);
    } else {
      offers.lowPrice = low.toFixed(2);
      offers.highPrice = high.toFixed(2);
      offers.offerCount = String(offerCount);
    }
  } else {
    offers = {
      '@type': 'Offer',
      url,
      priceCurrency: currency,
      availability,
    };
  }

  const location = {
    '@type': 'Place',
    name: venueName(event),
    address: {
      '@type': 'PostalAddress',
      addressLocality: city,
      addressCountry: String(event.country || 'IL').toUpperCase(),
    },
  };

  const data = {
    '@context': 'https://schema.org',
    '@type': 'Event',
    name,
    startDate: event.date || event.event_date || event.startDate || undefined,
    eventAttendanceMode: 'https://schema.org/OfflineEventAttendanceMode',
    location,
    offers,
    url,
    description: String(event.seo_description || event.description || '').trim() || undefined,
  };

  const artistName =
    (typeof event.artist === 'object' && event.artist?.name) || event.artist_name || '';
  if (String(artistName).trim()) {
    data.performer = { '@type': 'PerformingGroup', name: String(artistName).trim() };
  }
  return data;
}

/** Single-ticket Offer wrapped in Event — used on /ticket/:id. */
export function buildTicketOfferJsonLd(ticket, path) {
  if (!ticket || typeof ticket !== 'object') return null;
  const eventName = String(ticket.event_name || ticket.event?.name || '').trim();
  if (!eventName) return null;
  const price = ticketPrice(ticket);
  const currency = String(ticket.currency || ticket.price_currency || 'ILS').trim() || 'ILS';
  const url = toPublicAbsoluteUrl(path || `/ticket/${ticket.id || ''}`);
  const qty = Number(ticket.available_quantity ?? ticket.quantity ?? 0);
  return {
    '@context': 'https://schema.org',
    '@type': 'Event',
    name: eventName,
    startDate: ticket.event_date || ticket.event?.date || undefined,
    location: {
      '@type': 'Place',
      name: String(ticket.venue || ticket.event?.venue || 'Israel').trim() || 'Israel',
    },
    offers: {
      '@type': 'Offer',
      url,
      priceCurrency: currency,
      ...(price != null ? { price: price.toFixed(2) } : {}),
      availability: qty > 0 ? 'https://schema.org/InStock' : 'https://schema.org/SoldOut',
    },
    url,
  };
}
