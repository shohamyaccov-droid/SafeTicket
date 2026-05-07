/**
 * Concert listings at Bloomfield: section strings → map block IDs (A1, 43, 77A, …).
 */

import { CONCERT_BLOCKS } from './bloomfieldConcertGeometry';
import {
  mockListingRating,
  normalizeSplitType,
} from './bloomfieldListing';

const VALID_IDS = new Set(CONCERT_BLOCKS.map((b) => b.id));

/**
 * @param {string|null|undefined} raw — e.g. "A1", "Section 43", "77a", "105"
 * @returns {string|null}
 */
export function concertBlockIdFromSection(raw) {
  if (raw == null) return null;
  let s = String(raw).trim();
  if (!s) return null;
  const upper = s.toUpperCase();

  let m = upper.match(/^SECTION\s+(.+)$/);
  if (m) s = m[1].trim();

  m = s.toUpperCase().match(/^([ABC])(\d{1,2})$/);
  if (m) {
    const id = `${m[1]}${m[2]}`;
    return VALID_IDS.has(id) ? id : null;
  }

  const compact = s.replace(/\s/g, '').toUpperCase();
  m = compact.match(/^([ABC])(\d{1,2})$/);
  if (m) {
    const id = `${m[1]}${m[2]}`;
    return VALID_IDS.has(id) ? id : null;
  }

  m = compact.match(/^(\d{2,3})([AB])$/);
  if (m) {
    const id = `${m[1]}${m[2]}`;
    return VALID_IDS.has(id) ? id : null;
  }

  m = compact.match(/^(\d{2,3})$/);
  if (m) {
    const id = m[1];
    return VALID_IDS.has(id) ? id : null;
  }

  return null;
}

function zoneFromBlockId(blockId) {
  if (!blockId) return 'pitch';
  const b = CONCERT_BLOCKS.find((x) => x.id === blockId);
  if (!b) return 'pitch';
  if (b.zone === 'west') return 'concert-west';
  if (b.zone === 'east') return 'concert-east';
  if (b.zone === 'south') return 'concert-south';
  return 'pitch';
}

function deriveClearView(ticket, rowStr) {
  const rowNum = parseInt(String(rowStr).replace(/\D/g, ''), 10);
  if (!Number.isNaN(rowNum) && rowNum <= 12) return true;
  let h = 0;
  const str = String(ticket?.id ?? rowStr ?? '0');
  for (let i = 0; i < str.length; i += 1) {
    h = (h << 5) - h + str.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h) % 3 === 0;
}

/**
 * @param {object} group
 * @param {string} stableGroupKey
 */
export function enrichBloomfieldConcertGroup(group, stableGroupKey) {
  const t = group?.tickets?.[0];
  const rawSec = t?.section != null ? String(t.section).trim() : '';
  const blockId = concertBlockIdFromSection(rawSec) ?? '';
  const zone = blockId ? zoneFromBlockId(blockId) : 'pitch';
  const row = t?.row || t?.seat_row || '—';
  const splitRaw = t?.split_type || t?.split_option || group?.split_type || '';
  const splitType = normalizeSplitType(splitRaw);
  const avail = group.available_count || 0;
  const together = splitType === 'pairs' || (splitType !== 'all' && avail >= 2);
  const clearView = deriveClearView(t, row);
  const rating = mockListingRating(stableGroupKey);
  const features = [];
  if (together) features.push({ key: 'together', label: '2 tickets together' });
  if (clearView) features.push({ key: 'view', label: 'Clear view' });
  const urgencyNote =
    avail > 0 && avail < 5
      ? `${avail} ticket${avail === 1 ? '' : 's'} remaining in this listing`
      : null;
  return {
    sectionId: rawSec || blockId,
    zone,
    blockId,
    row: String(row),
    rating,
    features,
    isTopChoice: rating.score >= 9.5,
    urgencyNote,
    lastTickets: avail <= 2,
    splitType,
  };
}
