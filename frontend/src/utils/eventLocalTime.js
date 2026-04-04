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
