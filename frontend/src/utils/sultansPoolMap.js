/** Sultan's Pool (בריכת הסולטן) — interactive seating map helpers. */

export const VENUE_SULTANS_POOL = 'בריכת הסולטן';

/** Clickable ticket zones. Stage (`stage`) is visual-only and omitted here. */
export const SULTANS_POOL_ZONES = [
  { id: 'orchestra', label: 'אורקסטרה' },
  { id: 'gush-1', label: 'גוש 1' },
  { id: 'gush-2', label: 'גוש 2' },
  { id: 'gush-3', label: 'גוש 3' },
  { id: 'gush-4', label: 'גוש 4' },
  { id: 'gush-5', label: 'גוש 5' },
  { id: 'accessible', label: 'מושבים נגישים' },
];

export const SULTANS_POOL_ZONE_IDS = SULTANS_POOL_ZONES.map((z) => z.id);

export const SULTANS_POOL_ZONE_LABELS = Object.fromEntries(
  SULTANS_POOL_ZONES.map((z) => [z.id, z.label])
);

export function isSultansPoolVenueName(venueName) {
  if (!venueName) return false;
  const v = String(venueName).trim();
  if (v === VENUE_SULTANS_POOL) return true;
  return v.includes('בריכת הסולטן') || /sultan'?s?\s*pool/i.test(v);
}

function sectionText(ticket) {
  if (!ticket) return '';
  return String(ticket.section || ticket.section_name || '').trim().replace(/\s+/g, ' ');
}

export function sultansPoolZoneIdFromTicket(ticket) {
  const raw = sectionText(ticket);
  if (!raw) return null;
  const lower = raw.toLowerCase();

  if (/אורקסטרה|orchestra/.test(lower) || /אורקסטרה/.test(raw)) return 'orchestra';
  if (/נגיש|accessible/.test(lower) || /נגיש/.test(raw)) return 'accessible';

  const gushHe = raw.match(/^גוש\s*(\d+)$/);
  if (gushHe && Number(gushHe[1]) >= 1 && Number(gushHe[1]) <= 5) return `gush-${gushHe[1]}`;
  const gushEn = lower.match(/^gush[-\s]?(\d+)$/);
  if (gushEn && Number(gushEn[1]) >= 1 && Number(gushEn[1]) <= 5) return `gush-${gushEn[1]}`;
  if (/^\d+$/.test(raw) && Number(raw) >= 1 && Number(raw) <= 5) return `gush-${raw}`;

  return null;
}

export function sultansPoolTicketMatchesZone(ticket, zoneId) {
  if (!zoneId) return false;
  return sultansPoolZoneIdFromTicket(ticket) === zoneId;
}

export function sultansPoolSellSectionOptions() {
  return SULTANS_POOL_ZONES.map((z) => ({
    value: z.label,
    label: z.label,
    structured: false,
  }));
}
