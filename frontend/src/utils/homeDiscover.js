/**
 * Homepage discovery helpers — performer grouping, last-minute filter, inventory flags.
 */
import { eventHref } from './eventSeo';
import { eventTicketCount } from './artistEventSupply';

/** @param {object} ev */
export function eventCategoryKey(ev) {
  const raw = ev?.category;
  if (raw == null || raw === '') return '';
  const s = String(raw).toLowerCase().trim();
  if (['concert', 'festival', 'sport', 'theater', 'standup'].includes(s)) return s;
  return s;
}

/** @param {object} ev */
export function performerKey(ev) {
  const id = ev?.artist_detail?.id ?? ev?.artist;
  if (id != null && id !== '') return `artist:${id}`;
  const name = String(ev?.artist_detail?.name ?? ev?.artist_name ?? '').trim();
  if (name) return `name:${name}`;
  const sport = eventCategoryKey(ev) === 'sport';
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
  if (eventCategoryKey(ev) === 'sport' && ev?.home_team && ev?.away_team) {
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
  if (eventCategory === 'sport') return 'sports';
  if (eventCategory === 'standup') return 'standup';
  if (eventCategory === 'theater') return 'theater';
  return 'music';
}

/**
 * @param {object[]} list — upcoming marketplace events (already filtered)
 * @returns {Array<{
 *   key: string,
 *   artistId: string|number|null,
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

    out.push({
      key: `perf-${performerKey(display)}`,
      artistId: artistId != null ? artistId : null,
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
 * Events starting within the next `days` days (inclusive), with inventory.
 * @param {object[]} list
 * @param {Date} todayStart
 * @param {number} days
 */
export function filterLastMinuteEvents(list, todayStart, days = 4) {
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
 * Multiple events → ArtistEventsPage (or a date picker when there is no artist id).
 *
 * @param {{ artistId?: string|number|null, events?: object[] }} group
 * @returns {{ type: 'event'|'artist'|'picker'|'none', href?: string }}
 */
export function performerNavigateTarget(group) {
  const stocked = performerEventsWithTickets(group);
  if (stocked.length === 1) {
    return { type: 'event', href: eventHref(stocked[0]) };
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
