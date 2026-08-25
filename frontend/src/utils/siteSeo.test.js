import { describe, expect, it } from 'vitest';
import { DEFAULT_SITE_TITLE, eventDocumentTitle } from './siteSeo';

describe('siteSeo', () => {
  it('builds an event title for rich search snippets', () => {
    expect(
      eventDocumentTitle({
        artistName: 'אייל גולן',
        venue: 'מנורה',
      }),
    ).toBe('כרטיסים לאייל גולן במנורה - TradeTix');
  });

  it('falls back to the default site title', () => {
    expect(eventDocumentTitle({})).toBe(DEFAULT_SITE_TITLE);
  });
});
