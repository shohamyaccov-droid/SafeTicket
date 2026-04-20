/**
 * Pais Arena Jerusalem — map block id from ticket section (101–122 lower, 301–330 upper).
 */

import { blockIdFromSectionNumber } from './jerusalemArenaGeometry';

export function extractJerusalemBlockId(ticket) {
  if (!ticket) return null;
  const raw = ticket.section_detail?.name || ticket.section || '';
  const s = String(raw).trim();
  const m3 = s.match(/\b(\d{3})\b/);
  if (m3) {
    const n = parseInt(m3[1], 10);
    if (n >= 101 && n <= 122) return String(n);
    if (n >= 301 && n <= 330) return String(n);
  }
  const numOnly = s.match(/\b(\d{1,2})\b/);
  if (numOnly) {
    const n = parseInt(numOnly[1], 10);
    const upper = /עליון|upper|עלי|300|level\s*3/i.test(s);
    if (upper && n >= 1 && n <= 30) return String(300 + n);
    if (!upper && n >= 1 && n <= 22) return String(100 + n);
  }
  return null;
}

export function enrichJerusalemGroup(group) {
  const t = group.tickets[0];
  const blockId = extractJerusalemBlockId(t) || blockIdFromSectionNumber(String(t?.section ?? ''));
  const n = parseInt(blockId, 10);
  return {
    blockId,
    sectionId: blockId,
    isLower: Number.isFinite(n) && n >= 101 && n <= 122,
  };
}
