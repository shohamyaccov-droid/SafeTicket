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
 * Add Cloudinary delivery optimizations (q_auto,f_auto,w_*) only for valid image/upload URLs.
 * Inserts the transformation chain immediately after .../image/upload/ and before version (v123) or public_id.
 * Skips if transformations already present (comma in first segment or known transform tokens).
 */
function cloudinaryOptimizedUrl(httpsUrl, maxWidth = 800) {
  const u = String(httpsUrl || '').trim();
  if (!u) return u;
  const m = u.match(/^(https?:\/\/res\.cloudinary\.com\/[^/]+\/)image\/upload\//i);
  if (!m) {
    return u;
  }
  const uploadPrefixLen = m[0].length;
  const suffix = u.slice(uploadPrefixLen);
  if (!suffix) return u;
  const firstSeg = suffix.split('/')[0] || '';
  if (!firstSeg) return u;
  if (/,/.test(firstSeg)) {
    return u;
  }
  if (/^v\d+$/i.test(firstSeg)) {
    return `${u.slice(0, uploadPrefixLen)}f_auto,q_auto,w_${maxWidth},c_limit/${suffix}`;
  }
  if (
    /^(f_|q_|w_|c_|h_|dpr_|ar_|bo_|e_|so_|t_|l_|u_|d_|s_|x_|y_|r_|a_|vc_|fn_|pg_|if_|dn_|g_|fl_|cs_)/i.test(
      firstSeg
    )
  ) {
    return u;
  }
  return `${u.slice(0, uploadPrefixLen)}f_auto,q_auto,w_${maxWidth},c_limit/${suffix}`;
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
