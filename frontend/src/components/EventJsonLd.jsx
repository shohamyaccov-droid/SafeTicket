import { Helmet } from 'react-helmet-async';
import { safeJsonLdString } from '../utils/eventSeo';

/**
 * Injects Schema.org Event JSON-LD for Google Rich Results.
 * Prefer server-provided `jsonLd` from the Django API (includes AggregateOffer).
 */
export default function EventJsonLd({ jsonLd }) {
  if (!jsonLd || typeof jsonLd !== 'object') return null;
  return (
    <Helmet>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: safeJsonLdString(jsonLd) }}
      />
    </Helmet>
  );
}
