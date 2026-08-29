/* eslint-disable react/prop-types */
import { Helmet } from 'react-helmet-async';
import { PUBLIC_SITE_ORIGIN, toPublicAbsoluteUrl } from '../utils/publicSite';
import { buildBreadcrumbJsonLd } from '../utils/breadcrumbSeo';
import JsonLdScript from './JsonLdScript';

export default function PageSeo({
  title,
  description,
  path = '/',
  jsonLd = null,
  breadcrumbs = null,
  robots = 'index, follow',
}) {
  const canonical = toPublicAbsoluteUrl(path.startsWith('/') ? path : `/${path}`);
  const crumbId = `breadcrumb-jsonld-${path.replace(/\W+/g, '-')}`;
  return (
    <>
      <Helmet>
        <title>{title}</title>
        <meta name="robots" content={robots} />
        <meta name="description" content={description} />
        <link rel="canonical" href={canonical} />
        <meta property="og:site_name" content="TradeTix" />
        <meta property="og:type" content="website" />
        <meta property="og:locale" content="he_IL" />
        <meta property="og:title" content={title} />
        <meta property="og:description" content={description} />
        <meta property="og:url" content={canonical} />
        <meta property="og:image" content={`${PUBLIC_SITE_ORIGIN}/og-share.png`} />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content={title} />
        <meta name="twitter:description" content={description} />
      </Helmet>
      {jsonLd ? <JsonLdScript id={`page-jsonld-${path.replace(/\W+/g, '-')}`} data={jsonLd} /> : null}
      {Array.isArray(breadcrumbs) && breadcrumbs.length ? (
        <JsonLdScript id={crumbId} data={buildBreadcrumbJsonLd(breadcrumbs)} />
      ) : null}
    </>
  );
}
