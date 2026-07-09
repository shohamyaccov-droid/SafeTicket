/**
 * Event datetime in listings/modals: show clock in user's locale and label as venue-local time + place.
 */

/** Legacy generic venue choice — display as country label. */
export const VENUE_OTHER_LEGACY = 'אחר';
export const VENUE_ISRAEL = 'ישראל';

const COUNTRY_HE = {
  IL: 'ישראל',
  US: 'ארצות הברית',
  GB: 'בריטניה',
  ES: 'ספרד',
  FR: 'צרפת',
  DE: 'גרמניה',
  IT: 'איטליה',
  GR: 'יוון',
  CY: 'קפריסין',
  AE: 'איחוד האמירויות',
};

export function localityLabelFromTicketLike(obj) {
  if (!obj || typeof obj !== 'object') return '';
  const city = String(obj.event_city ?? obj.city ?? '').trim();
  const venueRaw = String(obj.venue ?? obj.venue_display ?? '').trim();
  const venue = venueRaw === VENUE_OTHER_LEGACY ? VENUE_ISRAEL : venueRaw;
  const countryCode = String(obj.event_country ?? obj.country ?? '').trim().toUpperCase();
  if (city) return city;
  if (venue) return venue;
  if (countryCode && COUNTRY_HE[countryCode]) return COUNTRY_HE[countryCode];
  return countryCode || '';
}

/**
 * Compact artist-page row: "13 באוגוסט 2026 | 20:30" (no seconds, timezone, or locality suffix).
 */
export function formatArtistEventRowDate(dateString) {
  if (!dateString) return 'תאריך בהמשך';
  try {
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return 'תאריך בהמשך';
    const datePart = new Intl.DateTimeFormat('he-IL', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(date);
    const timePart = new Intl.DateTimeFormat('he-IL', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(date);
    return `${datePart} | ${timePart}`;
  } catch {
    return 'תאריך בהמשך';
  }
}

/**
 * Map legacy "אחר" venue choice to buyer-facing country label "ישראל".
 */
export function normalizeVenueLabel(venue) {
  const v = String(venue || '').trim();
  if (!v || v === VENUE_OTHER_LEGACY || v === VENUE_ISRAEL) return VENUE_ISRAEL;
  return v;
}

/**
 * Full location line: "ישראל, תל אביב" or "היכל מנורה מבטחים, תל אביב".
 */
export function formatEventLocation(eventLike) {
  if (!eventLike || typeof eventLike !== 'object') return '';
  const city = String(eventLike.city || '').trim();
  const placeName = String(eventLike.venue_detail?.name || '').trim();

  if (placeName && placeName !== VENUE_OTHER_LEGACY) {
    return city ? `${placeName}, ${city}` : placeName;
  }

  const venue = normalizeVenueLabel(eventLike.venue);
  if (venue === VENUE_ISRAEL && city) return `${VENUE_ISRAEL}, ${city}`;
  if (venue && city) return `${venue}, ${city}`;
  return venue || city || '';
}

/**
 * Human venue label for listings — prefers structured place name over legacy "אחר".
 */
export function displayEventVenueName(eventLike) {
  if (!eventLike || typeof eventLike !== 'object') return 'מיקום לא צוין';
  const placeName = String(eventLike.venue_detail?.name || '').trim();
  const venue = normalizeVenueLabel(eventLike.venue);
  const city = String(eventLike.city || '').trim();

  if (placeName && placeName !== VENUE_OTHER_LEGACY) return placeName;
  if (venue && venue !== VENUE_ISRAEL) return venue;
  if (venue === VENUE_ISRAEL && city) return `${VENUE_ISRAEL}, ${city}`;
  if (city) return city;
  return 'מיקום לא צוין';
}

/**
 * Full listing line: date + time + "שעון מקומי [place]".
 */
export function formatEventDateTimeWithLocality(dateString, ticketLike) {
  if (!dateString) return 'TBA';
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return 'TBA';
    const datePart = new Intl.DateTimeFormat('he-IL', {
      weekday: 'short',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    }).format(date);
    const timePart = new Intl.DateTimeFormat('he-IL', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(date);
    const loc = localityLabelFromTicketLike(ticketLike);
    const suffix = loc ? ` שעון מקומי ${loc}` : ' (שעון מקומי)';
    return `${datePart}, ${timePart}${suffix}`;
  } catch {
    return 'TBA';
  }
}

/**
 * Compact: "20:00 שעון מקומי לונדון" for row subtitles.
 */
export function formatEventLocalTimeLine(dateString, ticketLike) {
  if (!dateString) return '';
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return '';
    const timePart = new Intl.DateTimeFormat('he-IL', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(date);
    const loc = localityLabelFromTicketLike(ticketLike);
    const suffix = loc ? ` שעון מקומי ${loc}` : ' שעון מקומי';
    return `${timePart}${suffix}`;
  } catch {
    return '';
  }
}
