/**
 * Homepage discovery helpers — performer grouping, last-minute filter, inventory flags.
 */
import { eventHref } from './eventSeo';
import { eventTicketCount } from './artistEventSupply';

/** Homepage last-minute row: upcoming events within this many days. */
export const LAST_MINUTE_WINDOW_DAYS = 14;

/** Homepage row order: last-minute, then recommended, then category rows. */
export const HOME_DISCOVER_ROW_ORDER = [
  'last-minute',
  'recommended',
  'music',
  'sports-season',
  'standup',
  'sports',
];

const commonsFile = (filename) =>
  `https://commons.wikimedia.org/wiki/Special:FilePath/${filename}?width=1200`;

/** Official club crests (Hebrew Wikipedia infobox) for the sports season homepage row. */
export const SPORT_TEAM_PLACEHOLDERS = {
  'מכבי חיפה':
    'https://upload.wikimedia.org/wikipedia/he/1/1e/%D7%A1%D7%9E%D7%9C_%D7%9E%D7%9B%D7%91%D7%99_%D7%97%D7%99%D7%A4%D7%94_2023.png',
  'מכבי תל אביב': 'https://upload.wikimedia.org/wikipedia/he/4/45/Maccabi_Tel_Aviv_FC.png',
  'בית"ר ירושלים': 'https://upload.wikimedia.org/wikipedia/he/3/31/BeitarJerusalemCrestStar2020.png',
  'הפועל באר שבע': 'https://upload.wikimedia.org/wikipedia/he/e/eb/LogoOfHBS.png',
  'הפועל תל אביב': 'https://upload.wikimedia.org/wikipedia/he/5/52/Hapoel_Tel_Aviv_Logo.png',
  'הפועל ירושלים':
    'https://upload.wikimedia.org/wikipedia/he/7/78/HapoelJerusalemFootballClubLogo2021.png',
};

/** Category fallbacks when the home/away team is not in SPORT_TEAM_PLACEHOLDERS. */
export const SPORT_EVENT_PLACEHOLDERS = {
  football: commonsFile('Ramat_Gan_Stadium_10.jpg'),
  basketball: commonsFile('Ramat_Gan_Stadium_10.jpg'),
};

export const SPORT_EVENT_CATEGORIES = ['sport', 'football', 'basketball'];
export const SEASON_SPORTS_CATEGORIES = ['football', 'basketball'];

/** Real artist photos (Wikimedia) when the catalog has no artist/event image. */
export const HOT_EVENT_PLACEHOLDERS = {
  _default: commonsFile('Ramat_Gan_Stadium_10.jpg'),
  'חנן בן ארי': commonsFile('%D7%97%D7%A0%D7%9F_%D7%91%D7%9F_%D7%90%D7%A8%D7%99.jpg'),
  'ישי ריבו': commonsFile('Yishai_Rivo6960.JPG'),
  טונה: commonsFile('%D7%90%D7%99%D7%AA%D7%99_%D7%96%D7%91%D7%95%D7%9C%D7%95%D7%9F_%D7%98%D7%95%D7%A0%D7%94.jpg'),
  פסטיגל:
    'https://upload.wikimedia.org/wikipedia/he/4/42/%D7%9E%D7%99%D7%99_%D7%A4%D7%A1%D7%98%D7%99%D7%92%D7%9C.jpg',
  'הדג נחש': 'https://upload.wikimedia.org/wikipedia/he/f/fa/HaDagNahash.jpg',
  'נועם בתן': commonsFile('Noam_Bettan_2.jpg'),
  'אגם בוחבוט': commonsFile('Agam_Buhbut_by_Pini_Siluk_%28cropped%29.jpg'),
  'שרית חדד': commonsFile('Sarit_Hadad.jpg'),
  NEXT: commonsFile('Ramat_Gan_Stadium_10.jpg'),
};

/** Attach a placeholder image_url when the event/artist has none. */
export function applyHotEventPlaceholder(ev) {
  if (!ev) return ev;
  if (ev.image_url || ev.artist_detail?.image_url) return ev;
  const name = String(ev.artist_detail?.name || ev.artist_name || '').trim();
  return { ...ev, image_url: HOT_EVENT_PLACEHOLDERS[name] || HOT_EVENT_PLACEHOLDERS._default };
}

/** Upcoming high-demand events, chronological. */
export function filterHighDemandEvents(list) {
  return [...(list || [])]
    .filter((ev) => Boolean(ev?.high_demand) && ev?.date)
    .sort((a, b) => new Date(a.date) - new Date(b.date));
}

/** Attach a club-crest placeholder when the sports event has no image. */
export function applySportEventPlaceholder(ev) {
  if (!ev) return ev;
  if (ev.image_url || ev.artist_detail?.image_url) return ev;
  const teamName = String(
    ev.artist_detail?.name || ev.artist_name || ev.home_team || '',
  ).trim();
  const teamUrl = SPORT_TEAM_PLACEHOLDERS[teamName];
  if (teamUrl) return { ...ev, image_url: teamUrl };
  const cat = eventCategoryKey(ev);
  return {
    ...ev,
    image_url: SPORT_EVENT_PLACEHOLDERS[cat] || SPORT_EVENT_PLACEHOLDERS.football,
  };
}

export function isSportEventCategory(ev) {
  return SPORT_EVENT_CATEGORIES.includes(eventCategoryKey(ev));
}

export function isSeasonSportsEvent(ev) {
  const cat = eventCategoryKey(ev);
  const hot = Boolean(ev?.high_demand || ev?.is_hot);
  return hot && SEASON_SPORTS_CATEGORIES.includes(cat);
}

/** Upcoming high-demand football/basketball matches, chronological. */
export function filterSeasonSportsEvents(list) {
  return [...(list || [])]
    .filter((ev) => isSeasonSportsEvent(ev) && ev?.date)
    .sort((a, b) => new Date(a.date) - new Date(b.date));
}

/** @param {object} ev */
export function eventCategoryKey(ev) {
  const raw = ev?.category;
  if (raw == null || raw === '') return '';
  const s = String(raw).toLowerCase().trim();
  if (['concert', 'festival', 'sport', 'football', 'basketball', 'theater', 'standup'].includes(s)) return s;
  return s;
}

/** @param {object} ev */
export function performerKey(ev) {
  const id = ev?.artist_detail?.id ?? ev?.artist;
  if (id != null && id !== '') return `artist:${id}`;
  const name = String(ev?.artist_detail?.name ?? ev?.artist_name ?? '').trim();
  if (name) return `name:${name}`;
  const sport = isSportEventCategory(ev);
  if (sport && ev?.home_team && ev?.away_team) {
    return `match:${ev.home_team}\u0000${ev.away_team}`;
  }
  const title = String(ev?.name ?? '').trim();
  if (title) return `title:${title}`;
  return `event:${ev?.id ?? 'unknown'}`;
}

/** @param {object} ev */
export function performerDisplayName(ev) {
  const fromArtist = ev?.artist_detail?.name || ev?.artist_name;
  if (fromArtist) return String(fromArtist).trim();
  if (isSportEventCategory(ev) && ev?.home_team && ev?.away_team) {
    const t = ev.tournament ? ` · ${ev.tournament}` : '';
    return `${ev.home_team} נגד ${ev.away_team}${t}`;
  }
  return String(ev?.name ?? 'אירוע').trim();
}

/** @param {object} ev */
export function performerImageUrl(ev) {
  return ev?.artist_detail?.image_url || ev?.image_url || '';
}

/** @param {object} ev */
export function performerCategory(ev) {
  const artistCategory = ev?.artist_detail?.category;
  if (artistCategory) return String(artistCategory).trim();
  const eventCategory = eventCategoryKey(ev);
  if (eventCategory === 'sport' || eventCategory === 'football' || eventCategory === 'basketball') return 'sports';
  if (eventCategory === 'standup') return 'standup';
  if (eventCategory === 'theater') return 'theater';
  return 'music';
}

/**
 * @param {object[]} list — upcoming marketplace events (already filtered)
 * @returns {Array<{
 *   key: string,
 *   artistId: string|number|null,
 *   artistSlug: string|null,
 *   performerName: string,
 *   imageUrl: string,
 *   events: object[],
 *   eventCount: number,
 *   totalTickets: number,
 *   nextDate: string|null,
 *   category: string,
 *   hasTickets: boolean,
 *   waitlistOnly: boolean,
 * }>}
 */
export function groupEventsByPerformer(list) {
  const map = new Map();
  for (const ev of list || []) {
    const k = performerKey(ev);
    if (!map.has(k)) map.set(k, []);
    map.get(k).push(ev);
  }

  const out = [];
  for (const events of map.values()) {
    if (!events.length) continue;
    events.sort((a, b) => new Date(a.date) - new Date(b.date));
    const display = events[0];
    const totalTickets = events.reduce((acc, e) => acc + eventTicketCount(e), 0);
    const hasTickets = totalTickets > 0;
    const waitlistOnly = !hasTickets && events.some((e) => Boolean(e.high_demand));
    const artistId = display.artist_detail?.id ?? display.artist ?? null;
    const artistSlug = display.artist_detail?.slug || display.artist?.slug || null;

    out.push({
      key: `perf-${performerKey(display)}`,
      artistId: artistId != null ? artistId : null,
      artistSlug: artistSlug || null,
      performerName: performerDisplayName(display),
      imageUrl: performerImageUrl(display),
      category: performerCategory(display),
      events,
      eventCount: events.length,
      totalTickets,
      nextDate: display.date ?? null,
      hasTickets,
      waitlistOnly,
    });
  }

  return out;
}

/**
 * Events starting within the next `days` days (inclusive of today, exclusive of past).
 * @param {object[]} list
 * @param {Date} todayStart
 * @param {number} days
 */
export function filterLastMinuteEvents(list, todayStart, days = LAST_MINUTE_WINDOW_DAYS) {
  const end = new Date(todayStart);
  end.setDate(end.getDate() + days);
  end.setHours(23, 59, 59, 999);

  return (list || [])
    .filter((ev) => {
      if (!ev?.date) return false;
      const d = new Date(ev.date);
      if (Number.isNaN(d.getTime())) return false;
      if (d < todayStart || d > end) return false;
      return eventTicketCount(ev) > 0;
    })
    .sort((a, b) => new Date(a.date) - new Date(b.date));
}

/** Sort performer groups by live inventory first, then demand, then name. */
export function sortPerformersByDemand(groups) {
  return [...groups].sort((a, b) => {
    const aTickets = Number(a?.totalTickets) || 0;
    const bTickets = Number(b?.totalTickets) || 0;
    const aHas = aTickets > 0 ? 1 : 0;
    const bHas = bTickets > 0 ? 1 : 0;
    if (aHas !== bHas) return bHas - aHas;
    if (aTickets !== bTickets) return bTickets - aTickets;
    return String(a?.performerName || '').localeCompare(String(b?.performerName || ''), 'he');
  });
}

/** Upcoming events on a performer card that still have live inventory. */
export function performerEventsWithTickets(group) {
  return (group?.events || []).filter((ev) => eventTicketCount(ev) > 0);
}

/**
 * Homepage performer-card destination.
 * One upcoming event with tickets → EventDetailsPage.
 * Multiple events → ArtistPage (or a date picker when there is no artist id).
 *
 * @param {{ artistId?: string|number|null, artistSlug?: string|null, events?: object[] }} group
 * @returns {{ type: 'event'|'artist'|'picker'|'none', href?: string }}
 */
export function performerNavigateTarget(group) {
  const stocked = performerEventsWithTickets(group);
  if (stocked.length === 1) {
    return { type: 'event', href: eventHref(stocked[0]) };
  }
  if (group?.artistSlug) {
    return { type: 'artist', href: `/artist/${group.artistSlug}` };
  }
  if (group?.artistId != null && group.artistId !== '') {
    return { type: 'artist', href: `/artist/${group.artistId}` };
  }
  if ((group?.events || []).length > 1) {
    return { type: 'picker' };
  }
  if ((group?.events || []).length === 1) {
    return { type: 'event', href: eventHref(group.events[0]) };
  }
  return { type: 'none' };
}
