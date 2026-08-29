/* eslint-disable react/prop-types */
import JsonLdScript from './JsonLdScript';
import { buildClientEventJsonLd } from '../utils/eventJsonLdClient';

/**
 * Injects Schema.org Event JSON-LD for Google Rich Results / AI Overviews.
 * Prefer server-provided `jsonLd` (Offer / AggregateOffer). Fall back to the live event + listings.
 */
export default function EventJsonLd({ jsonLd, event, tickets }) {
  const data =
    jsonLd && typeof jsonLd === 'object' && jsonLd['@type']
      ? jsonLd
      : buildClientEventJsonLd(event, tickets);
  if (!data || typeof data !== 'object') return null;
  return <JsonLdScript id="event-jsonld" data={data} />;
}
