/* eslint-disable react/prop-types */
import { useEffect } from 'react';
import { safeJsonLdString } from '../utils/eventSeo';

/**
 * Helmet often fails to persist <script type="application/ld+json"> in the live DOM.
 * Append the node to document.head so crawlers and DevTools see it after SPA navigation.
 */
export default function JsonLdScript({ data, id = 'tradetix-jsonld' }) {
  const payload = data && typeof data === 'object' ? safeJsonLdString(data) : '';

  useEffect(() => {
    if (!payload) return undefined;
    const existing = document.getElementById(id);
    if (existing) existing.remove();
    const el = document.createElement('script');
    el.type = 'application/ld+json';
    el.id = id;
    el.setAttribute('data-seo-jsonld', '1');
    el.text = payload;
    document.head.appendChild(el);
    return () => {
      el.remove();
    };
  }, [id, payload]);

  return null;
}
