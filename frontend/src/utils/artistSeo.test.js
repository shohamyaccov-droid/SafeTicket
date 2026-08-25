import { describe, expect, it } from 'vitest';
import {
  artistCanonicalPath,
  artistDocumentTitle,
  artistHrefFromEvent,
  artistHrefFromGroup,
  artistIntro,
  artistMetaDescription,
  artistTicketsHeading,
} from './artistSeo';

describe('artistSeo', () => {
  it('prefers slug over numeric id', () => {
    expect(artistCanonicalPath({ id: 12, slug: 'eyal-golan' })).toBe('/artist/eyal-golan');
    expect(artistCanonicalPath(12)).toBe('/artist/12');
  });

  it('builds SERP title and description for ticket searches', () => {
    expect(artistDocumentTitle('אייל גולן')).toBe(
      'כרטיסים לאייל גולן - לוח הופעות וכרטיסים יד שנייה | TradeTix',
    );
    expect(artistMetaDescription('אייל גולן')).toContain('מחפשים כרטיסים לאייל גולן');
    expect(artistTicketsHeading('אייל גולן')).toBe('כרטיסים לאייל גולן');
    expect(artistIntro('אייל גולן')).toContain('כרטיסים יד שנייה לאייל גולן');
  });

  it('resolves artist page hrefs from events and homepage groups', () => {
    expect(
      artistHrefFromEvent({ artist: { id: 7, slug: 'eyal-golan' } }),
    ).toBe('/artist/eyal-golan');
    expect(artistHrefFromEvent({ artist_detail: { id: 7 } })).toBe('/artist/7');
    expect(artistHrefFromGroup({ artistSlug: 'eyal-golan', artistId: 7 })).toBe(
      '/artist/eyal-golan',
    );
    expect(artistHrefFromGroup({ artistId: 7 })).toBe('/artist/7');
  });
});
