import { describe, expect, test } from 'vitest';
import { extractPaisArenaSectionId } from './paisArenaSectionMap';

describe('extractPaisArenaSectionId', () => {
  test('maps גוש 2 and אולם 2 onto lower-2 (inner ring)', () => {
    expect(extractPaisArenaSectionId({ section: 'גוש 2' })).toBe('lower-2');
    expect(extractPaisArenaSectionId({ venue_section: 'אולם 2' })).toBe('lower-2');
    expect(extractPaisArenaSectionId({ section: '2' })).toBe('lower-2');
  });

  test('maps 101-range and עליון/תחתון to the matching rings', () => {
    expect(extractPaisArenaSectionId({ section: '102' })).toBe('lower-2');
    expect(extractPaisArenaSectionId({ section: '2 תחתון' })).toBe('lower-2');
    expect(extractPaisArenaSectionId({ section: 'גוש 2 עליון' })).toBe('upper-2');
    expect(extractPaisArenaSectionId({ section: '302' })).toBe('upper-2');
  });

  test('maps VIP labels', () => {
    expect(extractPaisArenaSectionId({ section: 'VIP' })).toBe('vip');
    expect(extractPaisArenaSectionId({ section: 'VIP A' })).toBe('vip');
  });
});
