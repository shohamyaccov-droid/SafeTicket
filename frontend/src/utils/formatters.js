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

/**
 * Resolve catalog / media URLs for <img src>.
 * Absolute http(s) URLs (incl. signed Cloudinary) must be returned byte-for-byte after trim —
 * never append query params, transforms, or API origin.
 */
export const getFullImageUrl = (url, _opts = {}) => {
  if (url == null || url === 'undefined' || url === 'null' || typeof url === 'object') return null;
  const strUrl = String(url).trim();
  if (!strUrl || strUrl === 'undefined' || strUrl === 'null') return null;
  if (/^https?:\/\//i.test(strUrl)) {
    return strUrl;
  }
  if (strUrl.startsWith('//')) {
    return `https:${strUrl}`;
  }
  if (strUrl.startsWith('data:')) {
    return strUrl;
  }
  const normalized = strUrl.startsWith('/') ? strUrl : `/${strUrl}`;
  return `${apiOriginForImages()}${normalized}`;
};
