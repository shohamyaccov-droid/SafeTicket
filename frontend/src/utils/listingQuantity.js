/**
 * Quantity choices for a marketplace listing, matching checkout split rules.
 * Used on EventDetailsPage so buyers pick qty before PayMe, not in a second modal.
 */
export function normalizeListingSplitType(raw) {
  if (!raw) return 'any';
  const str = String(raw).trim().toLowerCase();
  if (str.includes('זוגות') || str.includes('pairs')) return 'pairs';
  if (str.includes('הכל') || str.includes('all')) return 'all';
  return 'any';
}

export function listingQuantityOptions(splitType, availableCount) {
  const max = Number(availableCount) || 0;
  if (max < 1) return [1];
  if (splitType === 'all') return [max];
  if (splitType === 'pairs') {
    const options = [];
    for (let i = 2; i <= max; i += 2) options.push(i);
    return options.length ? options : [max];
  }
  const options = [];
  for (let i = 1; i <= max; i += 1) options.push(i);
  return options;
}

export function defaultListingQuantity(splitType, availableCount) {
  const options = listingQuantityOptions(splitType, availableCount);
  return options[0] || 1;
}
