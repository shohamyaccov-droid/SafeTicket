/**
 * Sell-flow helpers: waitlist demand CTA and deep-link event preselect.
 */

export function parseSellPresetEventId(search) {
  if (search == null || search === '') return '';
  const raw =
    typeof search === 'string'
      ? search
      : typeof search.toString === 'function'
        ? search.toString()
        : '';
  const params = new URLSearchParams(raw.startsWith('?') ? raw.slice(1) : raw);
  return String(params.get('event') || params.get('event_id') || '').trim();
}

export function sellTicketsPathForEvent(eventOrId) {
  const id =
    eventOrId != null && typeof eventOrId === 'object' ? eventOrId.id : eventOrId;
  if (id == null || id === '') return '/sell/new';
  return `/sell/new?event=${encodeURIComponent(id)}`;
}

export function waitlistDemandCount(event) {
  const n = Number(event?.waitlist_count);
  if (!Number.isFinite(n) || n <= 0) return 0;
  return Math.floor(n);
}

export function sellerWaitlistCtaLabel(count) {
  return `🔥 ${count} אנשים מחכים עכשיו ברשימת ההמתנה לכרטיס הזה! יש לך כרטיס? לחץ כאן למכירה מהירה.`;
}

export function sellCategoryFromEvent(event) {
  const cat = String(event?.category || '').toLowerCase();
  if (['sport', 'football', 'basketball', 'משחקי ספורט', 'ספורט'].includes(cat)) {
    return 'sport';
  }
  if (['theater', 'הצגות תיאטרון', 'הצגה'].includes(cat)) return 'theater';
  if (['festival', 'פסטיבלים', 'פסטיבל'].includes(cat)) return 'festival';
  if (['standup', 'סטנדאפ'].includes(cat)) return 'standup';
  return 'concert';
}

export function artistIdFromEvent(event) {
  if (!event) return '';
  if (event.artist_id != null && event.artist_id !== '') return String(event.artist_id);
  const artist = event.artist;
  if (artist && typeof artist === 'object' && artist.id != null) return String(artist.id);
  if (artist != null && artist !== '') return String(artist);
  if (event.artist_detail?.id != null) return String(event.artist_detail.id);
  return '';
}

export function eventDisplayNameForSell(event) {
  if (!event) return '';
  if (
    ['sport', 'football', 'basketball', 'ספורט'].includes(String(event.category || '').toLowerCase()) &&
    event.home_team &&
    event.away_team
  ) {
    const tournamentStr = event.tournament ? ` - ${event.tournament}` : '';
    return `${event.home_team} vs ${event.away_team}${tournamentStr}`;
  }
  return event.name || (event.id != null ? `Event #${event.id}` : '');
}
