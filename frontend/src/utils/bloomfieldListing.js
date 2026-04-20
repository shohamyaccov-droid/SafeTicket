/**
 * Bloomfield stadium listing helpers: section → zone, mock rating/features, quantity filter.
 */

function simpleHash(str) {
  let h = 0;
  for (let i = 0; i < str.length; i += 1) {
    h = (h << 5) - h + str.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}

export function extractBloomfieldSectionNumber(ticket) {
  if (!ticket?.section) return null;
  const s = String(ticket.section);
  const m = s.match(/(\d{2,4})/);
  return m ? m[1] : null;
}

/** @returns {'north'|'south'|'east'|'west'} */
export function bloomfieldZoneFromSectionNumber(numStr) {
  if (!numStr) return 'south';
  const n = parseInt(numStr, 10);
  if (Number.isNaN(n)) return 'south';
  if (n >= 500) {
    return ['north', 'east', 'south', 'west'][n % 4];
  }
  if (n >= 400 && n < 500) return 'west';
  if (n >= 300 && n < 400) return 'east';
  if (n >= 200 && n < 300) return 'north';
  if (n >= 100 && n < 200) return 'south';
  return 'south';
}

export function mockListingRating(stableKey) {
  const h = simpleHash(String(stableKey ?? '0'));
  const score = Math.min(10, 8 + (h % 20) / 10);
  const rounded = Math.round(score * 10) / 10;
  let label = 'מעולה';
  if (rounded >= 9.8) label = 'מדהים';
  else if (rounded >= 9.2) label = 'מצוין';
  else if (rounded >= 8.7) label = 'טוב מאוד';
  return { score: rounded, label };
}

function deriveClearView(ticket, rowStr) {
  const rowNum = parseInt(String(rowStr).replace(/\D/g, ''), 10);
  if (!Number.isNaN(rowNum) && rowNum <= 12) return true;
  const h = simpleHash(String(ticket?.id ?? rowStr));
  return h % 3 === 0;
}

export function normalizeSplitType(rawSplitType) {
  if (!rawSplitType) return 'any';
  const str = String(rawSplitType).trim().toLowerCase();
  if (str.includes('זוגות') || str.includes('pairs')) return 'pairs';
  if (str.includes('הכל') || str.includes('all')) return 'all';
  return 'any';
}

/**
 * @param {object} group — ticket group from EventDetailsPage
 * @param {string} stableGroupKey — from stableListingGroupKey
 */
export function enrichBloomfieldGroup(group, stableGroupKey) {
  const t = group?.tickets?.[0];
  const sectionId = extractBloomfieldSectionNumber(t);
  const zone = bloomfieldZoneFromSectionNumber(sectionId);
  const row = t?.row || t?.seat_row || '—';
  const splitRaw = t?.split_type || t?.split_option || group?.split_type || '';
  const splitType = normalizeSplitType(splitRaw);
  const avail = group.available_count || 0;
  const together =
    splitType === 'pairs' || (splitType !== 'all' && avail >= 2);
  const clearView = deriveClearView(t, row);
  const rating = mockListingRating(stableGroupKey);
  const features = [];
  if (together) {
    features.push({ key: 'together', label: `${Math.min(2, avail)} כרטיסים יחד` });
  }
  if (clearView) {
    features.push({ key: 'view', label: 'נוף פתוח' });
  }
  const urgencyNote =
    avail > 0 && avail <= 3
      ? `${avail} כרטיסים נותרו במודעה זו`
      : null;
  return {
    sectionId: sectionId || '—',
    zone,
    row: String(row),
    rating,
    features,
    isTopChoice: rating.score >= 9.5,
    urgencyNote,
    lastTickets: avail <= 2,
    splitType,
  };
}

export function groupMatchesTicketQuantity(group, wantQty) {
  const w = Number(wantQty) || 1;
  if (w < 1) return true;
  const avail = group.available_count || 0;
  if (avail < w) return false;
  const first = group.tickets?.[0];
  const split = normalizeSplitType(
    first?.split_type || first?.split_option || group.split_type || ''
  );
  if (split === 'pairs') {
    if (w === 1) return false;
    return w % 2 === 0 && w <= avail;
  }
  if (split === 'all') {
    return w === avail;
  }
  return w <= avail;
}
