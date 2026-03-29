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
 * Insert Cloudinary auto format/quality + max width for responsive images (WhatsApp / mobile friendly).
 */
function cloudinaryOptimizedUrl(httpsUrl, maxWidth = 800) {
  const u = String(httpsUrl || '');
  if (!/res\.cloudinary\.com\/.+\/image\/upload\//i.test(u)) {
    return u;
  }
  if (/upload\/[^/]*\b(f_auto|q_auto|w_\d+)/i.test(u)) {
    return u;
  }
  return u.replace('/image/upload/', `/image/upload/f_auto,q_auto,w_${maxWidth},c_limit/`);
}

/**
 * @param {string|null|undefined} url
 * @param {{ maxWidth?: number }} [opts]
 */
export const getFullImageUrl = (url, opts = {}) => {
  const maxWidth = opts.maxWidth ?? 800;
  if (!url || url === 'undefined' || url === 'null' || typeof url === 'object') return null;
  const strUrl = String(url).trim();
  if (!strUrl || strUrl === 'undefined' || strUrl === 'null') return null;
  if (strUrl.startsWith('http')) {
    return cloudinaryOptimizedUrl(strUrl, maxWidth);
  }
  const normalized = strUrl.startsWith('/') ? strUrl : `/${strUrl}`;
  const abs = `${apiOriginForImages()}${normalized}`;
  return cloudinaryOptimizedUrl(abs, maxWidth);
};
