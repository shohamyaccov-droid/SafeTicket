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
