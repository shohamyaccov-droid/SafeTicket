/**
 * Pais Arena Jerusalem — map block id from ticket section text (101–112 lower, 201–212 upper).
 */

import { blockIdFromSectionNumber } from './jerusalemArenaGeometry';

export function extractJerusalemBlockId(ticket) {
  if (!ticket) return null;
  const raw = ticket.section_detail?.name || ticket.section || '';
  const s = String(raw).trim();
  const m = s.match(/\b(10[1-9]|11[0-2]|20[1-9]|21[0-2])\b/);
  if (m) return m[1];
  const numOnly = s.match(/\b([1-9]|1[0-2])\b/);
  if (numOnly) {
    const n = parseInt(numOnly[1], 10);
    const upper = /עליון|upper|עלי/i.test(s);
    if (upper) return String(200 + n);
    return String(100 + n);
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
    isLower: Number.isFinite(n) && n < 200,
  };
}
