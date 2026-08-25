/* eslint-disable react/prop-types */
import JsonLdScript from './JsonLdScript';

/**
 * Injects Schema.org Event JSON-LD for Google Rich Results.
 * Prefer server-provided `jsonLd` from the Django API (includes Offer / AggregateOffer).
 */
export default function EventJsonLd({ jsonLd }) {
  if (!jsonLd || typeof jsonLd !== 'object') return null;
  return <JsonLdScript id="event-jsonld" data={jsonLd} />;
}
