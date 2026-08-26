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

/** Hebrew / English listing strings → SVG zone ids (orchestra, gush-1…5, accessible). */
export const SULTANS_POOL_ZONE_ALIASES = {
  orchestra: 'orchestra',
  אורקסטרה: 'orchestra',
  'גוש אורקסטרה': 'orchestra',
  accessible: 'accessible',
  'מושבים נגישים': 'accessible',
  נגישים: 'accessible',
  נגיש: 'accessible',
  'gush-1': 'gush-1',
  'גוש 1': 'gush-1',
  1: 'gush-1',
  'gush-2': 'gush-2',
  'גוש 2': 'gush-2',
  2: 'gush-2',
  'gush-3': 'gush-3',
  'גוש 3': 'gush-3',
  3: 'gush-3',
  'gush-4': 'gush-4',
  'גוש 4': 'gush-4',
  4: 'gush-4',
  'gush-5': 'gush-5',
  'גוש 5': 'gush-5',
  5: 'gush-5',
};

export function isSultansPoolVenueName(venueName) {
  if (!venueName) return false;
  const v = String(venueName).trim();
  if (v === VENUE_SULTANS_POOL) return true;
  return v.includes('בריכת הסולטן') || /sultan'?s?\s*pool/i.test(v);
}

function stripGushPrefix(value) {
  let text = String(value || '').trim().replace(/\s+/g, ' ');
  while (/^גוש\s+/i.test(text) || /^gush\s+/i.test(text)) {
    text = text.replace(/^(גוש|gush)\s+/i, '').trim();
  }
  return text;
}

/**
 * Map a ticket section string or SVG id onto a Sultan's Pool zone id.
 * Accepts DB labels such as "גוש אורקסטרה", "אורקסטרה", "גוש 1".
 */
export function normalizeSultansPoolZoneId(value) {
  if (value == null) return null;
  const raw = String(value).trim().replace(/\s+/g, ' ');
  if (!raw) return null;
  if (SULTANS_POOL_ZONE_IDS.includes(raw)) return raw;

  const stripped = stripGushPrefix(raw);
  const alias =
    SULTANS_POOL_ZONE_ALIASES[raw] ||
    SULTANS_POOL_ZONE_ALIASES[stripped] ||
    SULTANS_POOL_ZONE_ALIASES[raw.toLowerCase()] ||
    SULTANS_POOL_ZONE_ALIASES[stripped.toLowerCase()];
  if (alias) return alias;

  if (/אורקסטרה|orchestra/i.test(raw)) return 'orchestra';
  if (/נגיש|accessible/i.test(raw)) return 'accessible';

  const gushHe = stripped.match(/^(\d+)$/) || raw.match(/^(?:גוש\s*)+(\d+)$/);
  if (gushHe && Number(gushHe[1]) >= 1 && Number(gushHe[1]) <= 5) return `gush-${gushHe[1]}`;
  const gushEn = stripped.toLowerCase().match(/^gush[-\s]?(\d+)$/);
  if (gushEn && Number(gushEn[1]) >= 1 && Number(gushEn[1]) <= 5) return `gush-${gushEn[1]}`;

  return null;
}

function sectionText(ticket) {
  if (!ticket) return '';
  const sources = [
    ticket.section,
    ticket.section_name,
    ticket.custom_section_text,
    ticket.section_legacy,
  ];
  for (const source of sources) {
    const text = String(source || '').trim().replace(/\s+/g, ' ');
    if (text) return text;
  }
  return '';
}

export function sultansPoolZoneIdFromTicket(ticket) {
  return normalizeSultansPoolZoneId(sectionText(ticket));
}

export function sultansPoolTicketMatchesZone(ticket, zoneId) {
  if (!zoneId) return false;
  const normalizedZone = normalizeSultansPoolZoneId(zoneId);
  return Boolean(normalizedZone) && sultansPoolZoneIdFromTicket(ticket) === normalizedZone;
}

export function sultansPoolSellSectionOptions() {
  return SULTANS_POOL_ZONES.map((z) => ({
    value: z.label,
    label: z.label,
    structured: false,
  }));
}
