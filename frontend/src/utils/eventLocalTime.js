/**
 * Event datetime in listings/modals: show clock in user's locale and label as venue-local time + place.
 */

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
  const venue = String(obj.venue ?? obj.venue_display ?? '').trim();
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
 * Human venue label for listings — prefers structured place name over legacy "אחר".
 */
export function displayEventVenueName(eventLike) {
  if (!eventLike || typeof eventLike !== 'object') return 'מיקום לא צוין';
  const placeName = String(eventLike.venue_detail?.name || '').trim();
  const venue = String(eventLike.venue || '').trim();
  const city = String(eventLike.city || '').trim();

  if (placeName && placeName !== 'אחר') return placeName;
  if (venue && venue !== 'אחר') return venue;
  if (placeName) return placeName;
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
