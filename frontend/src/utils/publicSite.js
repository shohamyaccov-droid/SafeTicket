/** Apex production origin for canonical / Open Graph URLs (never Render staging). */
export const PUBLIC_SITE_ORIGIN = 'https://tradetix.co.il';

const STAGING_HOST_RE = /https?:\/\/safeticket-web\.onrender\.com/i;
const WWW_HOST_RE = /https?:\/\/www\.tradetix\.co\.il/i;

/**
 * Normalize any absolute URL so crawlers always see the production apex domain.
 */
export function toPublicAbsoluteUrl(urlOrPath) {
  const raw = String(urlOrPath || '').trim();
  if (!raw) return PUBLIC_SITE_ORIGIN + '/';
  if (raw.startsWith('/')) {
    return `${PUBLIC_SITE_ORIGIN}${raw}`;
  }
  return raw
    .replace(STAGING_HOST_RE, PUBLIC_SITE_ORIGIN)
    .replace(WWW_HOST_RE, PUBLIC_SITE_ORIGIN);
}
