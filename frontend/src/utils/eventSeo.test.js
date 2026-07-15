/**
 * Event SEO path helpers + JSON-LD sanitization.
 */
import { describe, expect, it } from 'vitest';
import { eventCanonicalPath, eventHref, safeJsonLdString } from './eventSeo.js';

describe('eventSeo helpers', () => {
  it('prefers slug over id for href', () => {
    expect(eventHref({ id: 92, slug: 'eyal-golan-tel-aviv' })).toBe('/event/eyal-golan-tel-aviv');
    expect(eventHref({ id: 92 })).toBe('/event/92');
    expect(eventCanonicalPath('my-slug')).toBe('/event/my-slug');
  });

  it('escapes script-breaking characters in JSON-LD', () => {
    const raw = safeJsonLdString({ name: 'A</script>B', '@type': 'Event' });
    expect(raw).toContain('\\u003c');
    expect(raw).not.toContain('</script>');
  });
});
