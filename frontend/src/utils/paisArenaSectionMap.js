import { PAIS_ARENA_SECTIONS } from './paisArenaInteractiveGeometry';

const SECTION_BY_ID = Object.fromEntries(PAIS_ARENA_SECTIONS.map((s) => [s.id, s]));

function ticketSectionText(ticket) {
  if (!ticket) return '';
  return String(
    ticket.section_detail?.name
      || ticket.section
      || ticket.venue_section
      || ticket.block
      || '',
  ).trim();
}

/**
 * Map a Django ticket section string (גוש 2, אולם 2, 102, 2 עליון, VIP A)
 * onto a geometry id in paisArenaInteractiveGeometry.
 */
export function extractPaisArenaSectionId(ticket) {
  const s = ticketSectionText(ticket);
  if (!s) return null;
  const compact = s.replace(/\s+/g, ' ');

  if (/vip|ויפ/i.test(compact)) {
    if (SECTION_BY_ID.vip) return 'vip';
    const letter = compact.match(/vip\s*[-:]?\s*([a-g])/i)?.[1];
    if (letter) {
      const id = `vip-${letter.toUpperCase()}`;
      if (SECTION_BY_ID[id]) return id;
    }
  }

  const isUpper = /עליון|upper/i.test(compact);
  const isLower = /תחתון|lower/i.test(compact);

  const m3 = compact.match(/\b([13]\d{2})\b/);
  if (m3) {
    const n = parseInt(m3[1], 10);
    if (n >= 301 && n <= 330) {
      const i = n - 300;
      if (SECTION_BY_ID[`upper-${i}`]) return `upper-${i}`;
    }
    if (n >= 101 && n <= 122) {
      const i = n - 100;
      if (SECTION_BY_ID[`lower-${i}`]) return `lower-${i}`;
      if (SECTION_BY_ID[`floor-${i}`]) return `floor-${i}`;
    }
  }

  const mNum = compact.match(/(\d{1,2})/);
  if (!mNum) return null;
  const n = parseInt(mNum[1], 10);
  if (!Number.isFinite(n) || n < 1) return null;

  if (isUpper && SECTION_BY_ID[`upper-${n}`]) return `upper-${n}`;
  if (isLower && SECTION_BY_ID[`lower-${n}`]) return `lower-${n}`;
  if (SECTION_BY_ID[`floor-${n}`]) return `floor-${n}`;
  if (SECTION_BY_ID[`lower-${n}`]) return `lower-${n}`;
  if (SECTION_BY_ID[`upper-${n}`]) return `upper-${n}`;
  return null;
}

export function enrichPaisArenaGroup(group) {
  const t = group?.tickets?.[0];
  return {
    sectionId: extractPaisArenaSectionId(t),
  };
}
