/**
 * Artist hub path helpers for programmatic SEO routes.
 * Prefer slug when present; fall back to numeric id for legacy links.
 */
export function artistCanonicalPath(artistOrSlug) {
  if (artistOrSlug == null || artistOrSlug === '') return '/';
  if (typeof artistOrSlug === 'string' || typeof artistOrSlug === 'number') {
    return `/artist/${artistOrSlug}`;
  }
  const key = (artistOrSlug.slug && String(artistOrSlug.slug).trim()) || artistOrSlug.id;
  if (key == null || key === '') return '/';
  return `/artist/${key}`;
}

export function artistHref(artist) {
  return artistCanonicalPath(artist);
}

export function artistHrefFromEvent(event) {
  if (!event || typeof event !== 'object') return null;
  const nested =
    event.artist && typeof event.artist === 'object' ? event.artist : event.artist_detail;
  if (nested?.slug) return `/artist/${nested.slug}`;
  if (nested?.id != null && nested.id !== '') return `/artist/${nested.id}`;
  if (event.artist != null && typeof event.artist !== 'object') return `/artist/${event.artist}`;
  if (event.artist_id != null) return `/artist/${event.artist_id}`;
  return null;
}

export function artistHrefFromGroup(group) {
  if (group?.artistSlug) return `/artist/${group.artistSlug}`;
  if (group?.artistId != null && group.artistId !== '') return `/artist/${group.artistId}`;
  return null;
}

export function artistTicketsHeading(name) {
  return `כרטיסים ל${String(name || 'אמן').trim() || 'אמן'}`;
}

export function artistDocumentTitle(name) {
  const subject = String(name || 'אמן').trim() || 'אמן';
  return `כרטיסים ל${subject} - לוח הופעות וכרטיסים יד שנייה | TradeTix`;
}

export function artistMetaDescription(name) {
  const subject = String(name || 'אמן').trim() || 'אמן';
  return (
    `מחפשים כרטיסים ל${subject}? כל המועדים והכרטיסים הכי שווים מחכים לכם ב-TradeTix. ` +
    'קנייה ומכירה בטוחה ללא ספסרות.'
  );
}

export function artistIntro(name) {
  const subject = String(name || 'אמן').trim() || 'אמן';
  return (
    `כאן תמצאו את כל המועדים, ההופעות והכרטיסים יד שנייה ל${subject}. ` +
    'קנייה ומכירה מאובטחת.'
  );
}
