/**
 * Server-side SEO injection for the public frontend host (tradetix.co.il).
 *
 * A pure Vite CSR SPA only exposes generic index.html meta to crawlers that do not
 * execute JS. This Node shell keeps the Vite assets, injects <title>/Open Graph/JSON-LD,
 * and embeds static article HTML inside #root for / , /how-it-works, /how-to-sell, /faq, /event/*, and /artist/*.
 *
 * Start: node seo-server.mjs  (Render startCommand)
 */
import express from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { getStaticPageSeo } from './src/content/staticPagesSeo.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DIST = path.join(__dirname, 'dist');
const INDEX = path.join(DIST, 'index.html');
const API = (process.env.VITE_API_URL || process.env.API_URL || 'https://safeticket-api.onrender.com').replace(
  /\/$/,
  ''
);
const PORT = Number(process.env.PORT || 3000);
/** Public apex for robots/sitemap — never the Render staging hostname. */
const PUBLIC_ORIGIN = (
  process.env.PUBLIC_SITE_ORIGIN ||
  process.env.VITE_PUBLIC_SITE_ORIGIN ||
  'https://tradetix.co.il'
).replace(/\/$/, '');

const INDEX_CACHE = { html: '', mtime: 0 };

function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function injectSeo(html, seo) {
  const title = esc(seo.seo_title || 'TradeTix');
  const description = esc(seo.seo_description || '');
  const canonical = esc(seo.canonical_url || '');
  const ogImage = esc(seo.og_image || `${PUBLIC_ORIGIN}/og-share.png`);
  const scripts = [];
  const pushLd = (data, id) => {
    if (!data) return;
    scripts.push(
      `<script type="application/ld+json" id="${id}">${JSON.stringify(data).replace(/</g, '\\u003c')}</script>`,
    );
  };
  pushLd(seo.json_ld || {}, 'tradetix-jsonld');
  pushLd(seo.breadcrumb_json_ld, 'tradetix-breadcrumb-jsonld');
  const extra = Array.isArray(seo.extra_json_ld)
    ? seo.extra_json_ld
    : seo.extra_json_ld
      ? [seo.extra_json_ld]
      : [];
  extra.forEach((node, index) => pushLd(node, `tradetix-extra-jsonld-${index}`));
  const crawlerHtml = String(seo.crawler_html || '').trim();

  html = html.replace(/<title>[^<]*<\/title>/i, `<title>${title}</title>`);
  html = html.replace(/<meta\s+name=["']description["'][^>]*>/gi, '');
  html = html.replace(/<meta\s+name=["']robots["'][^>]*>/gi, '');
  html = html.replace(/<link\s+rel=["']canonical["'][^>]*>/gi, '');
  html = html.replace(/<meta\s+property=["']og:[^"']+["'][^>]*>/gi, '');
  html = html.replace(/<meta\s+name=["']twitter:[^"']+["'][^>]*>/gi, '');

  const block = `
    <!-- TradeTix SEO (Node inject; crawler-visible) -->
    <meta name="robots" content="index, follow" />
    <meta name="description" content="${description}" />
    <link rel="canonical" href="${canonical}" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="TradeTix" />
    <meta property="og:locale" content="he_IL" />
    <meta property="og:title" content="${title}" />
    <meta property="og:description" content="${description}" />
    <meta property="og:url" content="${canonical}" />
    <meta property="og:image" content="${ogImage}" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="${title}" />
    <meta name="twitter:description" content="${description}" />
    <meta name="twitter:image" content="${ogImage}" />
    ${scripts.join('\n    ')}
  `;
  html = html.replace(/<\/head>/i, `${block}</head>`);
  if (crawlerHtml) {
    return html.replace('<div id="root"></div>', `<div id="root">${crawlerHtml}</div>`);
  }
  const noscript = `<noscript><article><h1>${title}</h1><p>${description}</p></article></noscript>`;
  return html.replace('<div id="root"></div>', `<div id="root"></div>${noscript}`);
}

function readIndex() {
  if (!fs.existsSync(INDEX)) {
    throw new Error(`Missing ${INDEX} — run npm run build first`);
  }
  const mtime = fs.statSync(INDEX).mtimeMs;
  if (INDEX_CACHE.html && INDEX_CACHE.mtime === mtime) {
    return INDEX_CACHE.html;
  }
  INDEX_CACHE.html = fs.readFileSync(INDEX, 'utf8');
  INDEX_CACHE.mtime = mtime;
  return INDEX_CACHE.html;
}

function sendHtml(res, html, cacheControl) {
  res.set('Cache-Control', cacheControl);
  res.type('html').send(html);
}

const app = express();

app.get('/robots.txt', (_req, res) => {
  res
    .type('text/plain')
    .set('Cache-Control', 'public, max-age=3600')
    .send(`User-agent: *\nAllow: /\nSitemap: ${PUBLIC_ORIGIN}/sitemap.xml\n`);
});

app.get('/sitemap.xml', async (_req, res) => {
  try {
    const response = await fetch(`${API}/sitemap.xml`, {
      headers: { Accept: 'application/xml' },
    });
    if (response.ok) {
      const body = await response.text();
      if (body.includes('<urlset')) {
        res.type('application/xml').set('Cache-Control', 'public, max-age=300, stale-while-revalidate=3600').send(body);
        return;
      }
    }
  } catch (err) {
    console.warn('[seo-server] sitemap proxy failed:', err?.message || err);
  }
  const staticLocs = ['/', '/how-it-works', '/how-to-sell', '/faq', '/about', '/contact', '/terms', '/privacy', '/refunds', '/buyer-guarantee', '/accessibility', '/sell/new'];
  const urls = staticLocs.map((p) => (p === '/' ? `${PUBLIC_ORIGIN}/` : `${PUBLIC_ORIGIN}${p}`));
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (loc) => `  <url>
    <loc>${esc(loc)}</loc>
    <changefreq>weekly</changefreq>
  </url>`
  )
  .join('\n')}
</urlset>
`;
  res.type('application/xml').set('Cache-Control', 'public, max-age=120').send(body);
});

app.get('/.well-known/apple-developer-merchantid-domain-association', async (_req, res) => {
  try {
    const response = await fetch(`${API}/.well-known/apple-developer-merchantid-domain-association`);
    const body = await response.text();
    res
      .status(response.status)
      .type('text/plain')
      .set('Cache-Control', 'no-store, must-revalidate')
      .send(body);
  } catch (err) {
    res.status(502).type('text/plain').send('association unavailable');
  }
});

app.get('/event/:eventKey', async (req, res) => {
  let html = readIndex();
  try {
    const key = encodeURIComponent(req.params.eventKey);
    const response = await fetch(`${API}/api/users/events/${key}/seo/`, {
      headers: { Accept: 'application/json' },
    });
    if (response.ok) {
      const seo = await response.json();
      html = injectSeo(html, seo);
    }
  } catch (err) {
    console.warn('[seo-server] event SEO fetch failed:', err?.message || err);
  }
  sendHtml(res, html, 'public, max-age=60, stale-while-revalidate=300');
});

app.get('/artist/:artistKey', async (req, res) => {
  let html = readIndex();
  try {
    const key = encodeURIComponent(req.params.artistKey);
    const response = await fetch(`${API}/api/users/artists/${key}/seo/`, {
      headers: { Accept: 'application/json' },
    });
    if (response.ok) {
      const seo = await response.json();
      html = injectSeo(html, seo);
    }
  } catch (err) {
    console.warn('[seo-server] artist SEO fetch failed:', err?.message || err);
  }
  sendHtml(res, html, 'public, max-age=60, stale-while-revalidate=300');
});

function sendStaticMarketingPage(req, res) {
  const page = getStaticPageSeo(req.path, PUBLIC_ORIGIN);
  let html = readIndex();
  if (page) {
    html = injectSeo(html, page);
  }
  sendHtml(res, html, 'public, max-age=300, stale-while-revalidate=3600');
}

app.get('/', sendStaticMarketingPage);
app.get('/how-it-works', sendStaticMarketingPage);
app.get('/how-to-sell', sendStaticMarketingPage);
app.get('/faq', sendStaticMarketingPage);

app.use(express.static(DIST, { index: false, maxAge: '1h' }));

app.get('*', (req, res) => {
  const page = getStaticPageSeo(req.path, PUBLIC_ORIGIN);
  let html = readIndex();
  if (page) {
    html = injectSeo(html, page);
  }
  sendHtml(res, html, 'public, max-age=60, stale-while-revalidate=300');
});

app.listen(PORT, () => {
  console.log(`[seo-server] listening on :${PORT} api=${API}`);
});
