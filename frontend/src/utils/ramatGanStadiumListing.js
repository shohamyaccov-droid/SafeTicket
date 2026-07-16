import { INTERACTIVE_STADIUM_SECTION_IDS } from './ramatGanStadiumGeometry.generated.js';
import { isListingGroupTaken } from './ticketAvailability.js';
import { isListingGroupBuyable } from './mapSectionStatus.js';

const SECTION_ID_SET = new Set(INTERACTIVE_STADIUM_SECTION_IDS);

/**
 * Normalize ticket.section to InteractiveStadiumMap section id (e.g. "11A", "2-3").
 * @param {string|null|undefined} raw
 * @returns {string|null}
 */
export function ramatGanSectionIdFromSection(raw) {
  if (raw == null || raw === '') return null;
  let s = String(raw).trim();
  s = s.replace(/^גוש\s*/i, '').replace(/^section\s*/i, '').trim();
  const compact = s.replace(/\s+/g, '').toUpperCase();
  if (SECTION_ID_SET.has(compact)) return compact;
  if (SECTION_ID_SET.has(s)) return s;
  const hyphenMatch = compact.match(/^(\d)-(\d)$/);
  if (hyphenMatch) {
    const id = `${hyphenMatch[1]}-${hyphenMatch[2]}`;
    if (SECTION_ID_SET.has(id)) return id;
  }
  return null;
}

/**
 * @param {{ section?: string }|null|undefined} ticket
 * @returns {string|null}
 */
export function ramatGanSectionIdFromTicket(ticket) {
  if (!ticket) return null;
  return ramatGanSectionIdFromSection(ticket.section);
}

/**
 * @param {Array<{ tickets: object[], price: number|string, available_count?: number, is_taken?: boolean }>} ticketGroups
 * @returns {Record<string, { ticketsLeft: number, minPrice: number|null, status: 'available'|'taken' }>}
 */
export function buildRamatGanActiveListingsSummary(ticketGroups) {
  /** @type {Record<string, { ticketsLeft: number, minPrice: number|null, status: 'available'|'taken' }>} */
  const summary = {};
  for (const group of ticketGroups || []) {
    const first = group.tickets?.[0];
    const sectionId = ramatGanSectionIdFromTicket(first);
    if (!sectionId) continue;
    const price = parseFloat(group.price);
    const buyable = isListingGroupBuyable(group);
    const taken = isListingGroupTaken(group);
    if (!buyable && !taken) continue;
    if (buyable && Number.isNaN(price)) continue;

    const prev = summary[sectionId];
    if (buyable) {
      const qty = Number(group.available_count) || 0;
      if (qty <= 0) continue;
      if (!prev || prev.status !== 'available') {
        summary[sectionId] = {
          ticketsLeft: qty,
          minPrice: price,
          status: 'available',
        };
      } else {
        summary[sectionId] = {
          ticketsLeft: prev.ticketsLeft + qty,
          minPrice: Math.min(prev.minPrice, price),
          status: 'available',
        };
      }
    } else if (taken && (!prev || prev.status !== 'available')) {
      summary[sectionId] = {
        ticketsLeft: 0,
        minPrice: Number.isFinite(price) ? price : prev?.minPrice ?? null,
        status: 'taken',
      };
    }
  }
  return summary;
}
