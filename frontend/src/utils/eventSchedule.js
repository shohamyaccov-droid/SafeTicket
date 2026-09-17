/**
 * Upcoming vs past event dates for EventDetailsPage and homepage routing.
 */

export function isEventDatePassed(dateValue, now = new Date()) {
  if (!dateValue) return false;
  const d = new Date(dateValue);
  if (Number.isNaN(d.getTime())) return false;
  return d.getTime() < now.getTime();
}

export function eventArtistId(event) {
  if (!event || typeof event !== 'object') return null;
  if (event.artist && typeof event.artist === 'object' && event.artist.id != null) {
    return event.artist.id;
  }
  if (event.artist_detail?.id != null) return event.artist_detail.id;
  if (event.artist != null && typeof event.artist !== 'object') return event.artist;
  return event.artist_id ?? null;
}

export function normalizeArtistEventsPayload(data) {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.results)) return data.results;
  return [];
}

/**
 * Next date for this artist after a past event.
 * Prefer a future date that still has tickets; otherwise the soonest future date.
 */
export function pickNextUpcomingEvent(events, { now = new Date(), excludeId = null } = {}) {
  const upcoming = (events || [])
    .filter((ev) => ev && !isEventDatePassed(ev.date, now))
    .filter((ev) => {
      if (excludeId == null || excludeId === '') return true;
      const key = String(excludeId);
      return String(ev.id) !== key && String(ev.slug || '') !== key;
    })
    .sort((a, b) => new Date(a.date) - new Date(b.date));
  const withTickets = upcoming.filter((ev) => (Number(ev.tickets_count) || 0) > 0);
  return withTickets[0] || upcoming[0] || null;
}

function eventNameKey(event) {
  return String(event?.name || '').trim().toLowerCase();
}

function performerBlob(event) {
  return [
    event?.artist_detail?.name,
    event?.artist_name,
    event?.artist?.name,
    event?.name,
  ]
    .filter(Boolean)
    .join(' ');
}

export function isNextPerformer(event) {
  return /\bNEXT\b/i.test(performerBlob(event));
}

export function isHysteriaPerformer(event) {
  return /היסטריה/.test(performerBlob(event));
}

/** Mega-events whose dates must stay split by city/venue on homepage + event pages. */
export function isLocationSplitPerformer(event) {
  return isNextPerformer(event) || isHysteriaPerformer(event);
}

export function nextLocationKey(event) {
  const blob = [
    event?.venue,
    event?.venue_place?.name,
    event?.venue_detail?.name,
    event?.city,
    event?.name,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  if (/ירושל|פיס|י-ם|pais/.test(blob)) return 'jerusalem';
  if (/רמת גן|ר"ג|ר״ג|ramat/.test(blob)) return 'ramat-gan';
  if (/מנורה|תל אביב|tel.?aviv/.test(blob)) return 'tel-aviv';
  return 'other';
}

export function nextLocationDisplayName(locationKey) {
  if (locationKey === 'jerusalem') return 'NEXT - פיס ארנה ירושלים';
  if (locationKey === 'ramat-gan') return 'NEXT - אצטדיון רמת גן';
  return 'NEXT';
}

export function locationSplitDisplayName(event) {
  const loc = nextLocationKey(event);
  if (isHysteriaPerformer(event)) {
    if (loc === 'jerusalem') return 'היסטריה - ירושלים';
    return 'היסטריה - תל אביב';
  }
  if (isNextPerformer(event)) return nextLocationDisplayName(loc);
  return performerBlob(event) || 'אירוע';
}

function eventIdentityKey(event) {
  if (!event) return '';
  if (event.id != null && event.id !== '') return `id:${event.id}`;
  if (event.slug) return `slug:${String(event.slug).trim()}`;
  return '';
}

/**
 * Dates to show on an event page: prefer other performances with the same
 * show name; otherwise fall back to the artist's upcoming catalog.
 * Always includes the current event when it has a date.
 */
export function selectRelatedShowDates(artistEvents, currentEvent) {
  const list = Array.isArray(artistEvents) ? artistEvents.filter(Boolean) : [];
  const currentKey = eventIdentityKey(currentEvent);
  const nameKey = eventNameKey(currentEvent);
  const sameName = nameKey
    ? list.filter((ev) => eventNameKey(ev) === nameKey)
    : [];
  let pool = sameName.length >= 2 ? sameName : list;
  if (isLocationSplitPerformer(currentEvent)) {
    const loc = nextLocationKey(currentEvent);
    const sameVenue = list.filter((ev) => nextLocationKey(ev) === loc);
    pool = sameVenue.length ? sameVenue : [currentEvent].filter(Boolean);
  }

  const byId = new Map();
  for (const ev of pool) {
    const key = eventIdentityKey(ev) || `date:${ev.date}`;
    if (!byId.has(key)) byId.set(key, ev);
  }
  if (currentEvent && currentKey && !byId.has(currentKey)) {
    byId.set(currentKey, currentEvent);
  }

  return [...byId.values()].sort((a, b) => {
    const da = a?.date ? new Date(a.date).getTime() : 0;
    const db = b?.date ? new Date(b.date).getTime() : 0;
    return da - db;
  });
}
