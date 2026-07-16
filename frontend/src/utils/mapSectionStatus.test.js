import { describe, expect, it } from 'vitest';
import {
  buildSectionMapStatus,
  classifyMapBlockRows,
  isListingGroupBuyable,
  MAP_TAKEN_BUBBLE_LABEL,
} from './mapSectionStatus';

describe('mapSectionStatus', () => {
  const getSectionId = (t) => t.section;

  it('marks buyable sections available and prefers their min price', () => {
    const status = buildSectionMapStatus(
      [
        {
          price: 200,
          available_count: 2,
          tickets: [{ section: 'A', status: 'active' }],
        },
        {
          price: 150,
          available_count: 1,
          tickets: [{ section: 'A', status: 'active' }],
        },
      ],
      getSectionId
    );
    expect(status.A).toEqual({ status: 'available', minPrice: 150 });
    expect(isListingGroupBuyable({ available_count: 2, tickets: [{ status: 'active' }] })).toBe(
      true
    );
  });

  it('marks taken-only sections as taken', () => {
    const status = buildSectionMapStatus(
      [
        {
          price: 90,
          available_count: 0,
          is_taken: true,
          tickets: [{ section: 'B', status: 'taken' }],
        },
      ],
      getSectionId
    );
    expect(status.B.status).toBe('taken');
    expect(MAP_TAKEN_BUBBLE_LABEL).toBe('נתפס');
  });

  it('lets available win over taken in the same section', () => {
    const status = buildSectionMapStatus(
      [
        {
          price: 80,
          available_count: 0,
          tickets: [{ section: 'C', status: 'taken' }],
        },
        {
          price: 120,
          available_count: 1,
          tickets: [{ section: 'C', status: 'active' }],
        },
      ],
      getSectionId
    );
    expect(status.C).toEqual({ status: 'available', minPrice: 120 });
  });

  it('classifies block rows with available beating taken', () => {
    expect(
      classifyMapBlockRows([
        { group: { available_count: 0, tickets: [{ status: 'taken' }] } },
        { group: { available_count: 2, tickets: [{ status: 'active' }] } },
      ])
    ).toBe('available');
    expect(
      classifyMapBlockRows([
        { group: { available_count: 0, is_taken: true, tickets: [{ status: 'taken' }] } },
      ])
    ).toBe('taken');
    expect(classifyMapBlockRows([])).toBe('empty');
  });
});
