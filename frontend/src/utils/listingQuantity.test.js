import { describe, expect, it } from 'vitest';
import {
  defaultListingQuantity,
  listingQuantityOptions,
  normalizeListingSplitType,
} from './listingQuantity';

describe('listingQuantityOptions', () => {
  it('returns 1..n for any split', () => {
    expect(listingQuantityOptions('any', 3)).toEqual([1, 2, 3]);
  });

  it('returns even counts for pairs', () => {
    expect(listingQuantityOptions('pairs', 5)).toEqual([2, 4]);
  });

  it('locks to all available seats', () => {
    expect(listingQuantityOptions('all', 4)).toEqual([4]);
    expect(defaultListingQuantity('all', 4)).toBe(4);
  });

  it('normalizes Hebrew split labels', () => {
    expect(normalizeListingSplitType('נמכר בזוגות')).toBe('pairs');
    expect(normalizeListingSplitType('הכל יחד')).toBe('all');
    expect(normalizeListingSplitType('')).toBe('any');
  });
});
