export const getFullImageUrl = (url) => {
  if (!url || url === 'undefined' || url === 'null' || typeof url === 'object') return null;
  const strUrl = String(url).trim();
  if (!strUrl || strUrl === 'undefined' || strUrl === 'null') return null;
  if (strUrl.startsWith('http')) return strUrl;
  const normalized = strUrl.startsWith('/') ? strUrl : `/${strUrl}`;
  return `http://localhost:8000${normalized}`;
};

