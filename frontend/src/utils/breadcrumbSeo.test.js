import { describe, expect, it } from 'vitest';
import { buildBreadcrumbJsonLd, crumbs } from './breadcrumbSeo';

describe('buildBreadcrumbJsonLd', () => {
  it('maps Home → Event architecture for Google AI', () => {
    const data = buildBreadcrumbJsonLd(
      crumbs({ name: 'אייל גולן', path: '/artist/eyal-golan' }, { name: 'הופעה', path: '/event/eyal-golan-2026-08-29' }),
    );
    expect(data['@type']).toBe('BreadcrumbList');
    expect(data.itemListElement).toHaveLength(3);
    expect(data.itemListElement[0]).toMatchObject({
      '@type': 'ListItem',
      position: 1,
      name: 'דף הבית',
      item: 'https://tradetix.co.il/',
    });
    expect(data.itemListElement[2].item).toBe('https://tradetix.co.il/event/eyal-golan-2026-08-29');
  });
});
