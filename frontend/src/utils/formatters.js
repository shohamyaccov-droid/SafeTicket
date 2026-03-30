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
 * Do NOT mutate https URLs (Cloudinary signed URLs, delivery URLs, query params break if altered).
 */
export const getFullImageUrl = (url, _opts = {}) => {
  if (!url || url === 'undefined' || url === 'null' || typeof url === 'object') return null;
  const strUrl = String(url).trim();
  if (!strUrl || strUrl === 'undefined' || strUrl === 'null') return null;
  if (strUrl.startsWith('http')) {
    return strUrl;
  }
  const normalized = strUrl.startsWith('/') ? strUrl : `/${strUrl}`;
  return `${apiOriginForImages()}${normalized}`;
};
