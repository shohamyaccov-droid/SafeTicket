/**
 * Event page path helpers for programmatic SEO routes.
 * Prefer the ASCII artist-date slug when present; fall back to numeric id.
 */
export function eventCanonicalPath(eventOrSlug) {
  if (!eventOrSlug) return '/';
  if (typeof eventOrSlug === 'string' || typeof eventOrSlug === 'number') {
    return `/event/${eventOrSlug}`;
  }
  const key = (eventOrSlug.slug && String(eventOrSlug.slug).trim()) || eventOrSlug.id;
  return `/event/${key}`;
}

export function eventHref(event) {
  return eventCanonicalPath(event);
}

/** Ticket-group hub for all dates of the same show name. */
export function eventGroupHref(eventName) {
  const name = String(eventName || '').trim();
  if (!name) return '/';
  return `/event-group/${encodeURIComponent(name)}`;
}

/**
 * Sanitize JSON for embedding in <script type="application/ld+json">.
 */
export function safeJsonLdString(data) {
  return JSON.stringify(data ?? {}).replace(/</g, '\\u003c');
}
