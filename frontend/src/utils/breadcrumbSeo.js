import { PUBLIC_SITE_ORIGIN, toPublicAbsoluteUrl } from './publicSite';

/**
 * Schema.org BreadcrumbList for Google AI Overviews and traditional crawlers.
 * @param {{ name: string, path?: string, url?: string }[]} items
 */
export function buildBreadcrumbJsonLd(items = [], origin = PUBLIC_SITE_ORIGIN) {
  const list = (Array.isArray(items) ? items : [])
    .map((item) => ({
      name: String(item?.name || '').trim(),
      url: item?.url
        ? toPublicAbsoluteUrl(item.url)
        : item?.path
          ? toPublicAbsoluteUrl(item.path.startsWith('/') ? item.path : `/${item.path}`)
          : '',
    }))
    .filter((item) => item.name);

  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: list.map((item, index) => {
      const node = {
        '@type': 'ListItem',
        position: index + 1,
        name: item.name,
      };
      if (item.url) node.item = item.url;
      return node;
    }),
  };
}

export function homeBreadcrumb() {
  return { name: 'דף הבית', path: '/' };
}

export function crumbs(...items) {
  return [homeBreadcrumb(), ...items.filter(Boolean)];
}

export { PUBLIC_SITE_ORIGIN };
