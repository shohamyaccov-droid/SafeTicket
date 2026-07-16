/**
 * Shared venue-map section availability for social-proof coloring + bubbles.
 * Available listings win over taken when both exist in the same section.
 */

import { isListingGroupTaken } from './ticketAvailability';

/** Tailwind gray-300 — taken / disabled sections */
export const MAP_FILL_TAKEN = '#d1d5db';
/** Bright green — sections with buyable inventory */
export const MAP_FILL_AVAILABLE = '#4ade80';
/** Soft empty / no listing */
export const MAP_FILL_EMPTY = '#f3f4f6';
/** Hebrew label shown inside taken price bubbles (keeps map populated). */
export const MAP_TAKEN_BUBBLE_LABEL = 'נתפס';

export function isListingGroupBuyable(group) {
  if (!group) return false;
  if (isListingGroupTaken(group)) return false;
  return Number(group.available_count) > 0;
}

/**
 * @param {object} group
 * @param {(ticket: object, group: object) => string|null|undefined} getSectionId
 * @returns {Record<string, { status: 'available'|'taken', minPrice: number|null }>}
 */
export function buildSectionMapStatus(ticketGroups, getSectionId) {
  /** @type {Record<string, { status: 'available'|'taken', minPrice: number|null }>} */
  const out = {};
  for (const group of ticketGroups || []) {
    const first = group?.tickets?.[0];
    if (!first || typeof getSectionId !== 'function') continue;
    const sectionId = getSectionId(first, group);
    if (sectionId == null || sectionId === '') continue;
    const key = String(sectionId);
    const price = parseFloat(group.price);
    const minPrice = Number.isFinite(price) ? price : null;
    const buyable = isListingGroupBuyable(group);
    const taken = isListingGroupTaken(group);
    if (!buyable && !taken) continue;

    const prev = out[key];
    if (buyable) {
      if (!prev || prev.status !== 'available') {
        out[key] = { status: 'available', minPrice };
      } else if (
        minPrice != null &&
        (prev.minPrice == null || minPrice < prev.minPrice)
      ) {
        out[key] = { status: 'available', minPrice };
      }
    } else if (taken && (!prev || prev.status !== 'available')) {
      out[key] = {
        status: 'taken',
        minPrice:
          prev?.minPrice != null
            ? prev.minPrice
            : minPrice,
      };
    }
  }
  return out;
}

/** True when a Bloomfield/Jerusalem map row is permanently taken. */
export function mapRowIsTaken(row) {
  return isListingGroupTaken(row?.group);
}

/** True when a map row still has buyable seats. */
export function mapRowIsBuyable(row) {
  return isListingGroupBuyable(row?.group);
}

/**
 * Classify a block that has one or more listing rows.
 * @returns {'available'|'taken'|'empty'}
 */
export function classifyMapBlockRows(rows) {
  const list = Array.isArray(rows) ? rows : [];
  if (list.length === 0) return 'empty';
  if (list.some(mapRowIsBuyable)) return 'available';
  if (list.some(mapRowIsTaken)) return 'taken';
  return 'empty';
}
