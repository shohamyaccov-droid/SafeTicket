const apiOriginForImages = () => {
  const raw = (import.meta.env.VITE_API_URL || '').trim();
  if (raw) {
    return raw.replace(/\/api\/?$/i, '').replace(/\/+$/, '') || 'http://localhost:8000';
  }
  if (import.meta.env.PROD) {
    return 'https://safeticket-api.onrender.com';
  }
  return 'http://localhost:8000';
};

const CLOUDINARY_HOST_RE = /(?:^|\.)cloudinary\.com$/i;
const CLOUDINARY_DELIVERY_RE = /^(\/.+?\/(?:image|video|raw)\/(?:upload|fetch|private)\/)(.*)$/;

/**
 * Insert Cloudinary automatic format + quality on unsigned delivery URLs.
 * Signed paths (`s--…--`) are left untouched so the HMAC still matches.
 */
export function optimizeCloudinaryDeliveryUrl(url) {
  if (url == null || typeof url !== 'string') return url;
  const raw = url.trim();
  if (!raw) return url;
  const absolute = raw.startsWith('//') ? `https:${raw}` : raw;
  let parsed;
  try {
    parsed = new URL(absolute);
  } catch {
    return url;
  }
  if (!CLOUDINARY_HOST_RE.test(parsed.hostname)) {
    return parsed.toString();
  }
  if (parsed.pathname.includes('/s--')) {
    return parsed.toString();
  }
  const path = parsed.pathname;
  const hasAuto =
    /(^|\/|,)f_auto(,|\/|$)/.test(path) && /(^|\/|,)q_auto(,|\/|$)/.test(path);
  if (hasAuto) {
    return parsed.toString();
  }
  const match = path.match(CLOUDINARY_DELIVERY_RE);
  if (match) {
    parsed.pathname = `${match[1]}f_auto,q_auto/${match[2]}`;
    return parsed.toString();
  }
  if (!parsed.searchParams.has('q_auto')) {
    parsed.searchParams.set('q_auto', 'auto');
  }
  if (!parsed.searchParams.has('f_auto')) {
    parsed.searchParams.set('f_auto', 'auto');
  }
  return parsed.toString();
}

/**
 * Resolve catalog / media URLs for <img src>.
 * Relative media paths are prefixed with the API origin. Unsigned Cloudinary
 * delivery URLs get `f_auto,q_auto` so mobile clients receive compressed assets.
 */
export const getFullImageUrl = (url, _opts = {}) => {
  if (url == null || url === 'undefined' || url === 'null' || typeof url === 'object') return null;
  const strUrl = String(url).trim();
  if (!strUrl || strUrl === 'undefined' || strUrl === 'null') return null;
  if (/^https?:\/\//i.test(strUrl)) {
    return optimizeCloudinaryDeliveryUrl(strUrl);
  }
  if (strUrl.startsWith('//')) {
    return optimizeCloudinaryDeliveryUrl(`https:${strUrl}`);
  }
  if (strUrl.startsWith('data:') || strUrl.startsWith('blob:')) {
    return strUrl;
  }
  const normalized = strUrl.startsWith('/') ? strUrl : `/${strUrl}`;
  return `${apiOriginForImages()}${normalized}`;
};
