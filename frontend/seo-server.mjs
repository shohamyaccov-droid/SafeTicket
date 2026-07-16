/**
 * Server-side SEO injection for /event/* on the public frontend host.
 *
 * Why: A pure Vite CSR SPA only exposes the generic index.html meta tags to crawlers
 * that do not execute JS (and delays Googlebot indexing). This Node shell keeps the
 * same Vite assets, but fetches Django /events/:id/seo/ and injects <title>, meta,
 * Open Graph, and Schema.org Event JSON-LD into the first HTML byte.
 *
 * Start: node seo-server.mjs  (Render startCommand)
 */
import express from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

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
  const ogImage = esc(seo.og_image || '');
  const ld = JSON.stringify(seo.json_ld || {}).replace(/</g, '\\u003c');

  html = html.replace(/<title>[^<]*<\/title>/i, `<title>${title}</title>`);
  html = html.replace(/<meta\s+name=["']description["'][^>]*>/gi, '');
  html = html.replace(/<meta\s+name=["']robots["'][^>]*>/gi, '');
  html = html.replace(/<link\s+rel=["']canonical["'][^>]*>/gi, '');
  html = html.replace(/<meta\s+property=["']og:[^"']+["'][^>]*>/gi, '');
  html = html.replace(/<meta\s+name=["']twitter:[^"']+["'][^>]*>/gi, '');

  const block = `
    <!-- TradeTix event SEO (Node inject; crawler-visible) -->
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
    <script type="application/ld+json" id="tradetix-event-jsonld">${ld}</script>
  `;
  html = html.replace(/<\/head>/i, `${block}</head>`);
  const noscript = `<noscript><article><h1>${title}</h1><p>${description}</p></article></noscript>`;
  return html.replace('<div id="root"></div>', `<div id="root"></div>${noscript}`);
}

function readIndex() {
  if (!fs.existsSync(INDEX)) {
    throw new Error(`Missing ${INDEX} — run npm run build first`);
  }
  return fs.readFileSync(INDEX, 'utf8');
}

const app = express();

app.get('/robots.txt', (_req, res) => {
  res
    .type('text/plain')
    .set('Cache-Control', 'public, max-age=3600')
    .send(`User-agent: *\nAllow: /\nSitemap: ${PUBLIC_ORIGIN}/sitemap.xml\n`);
});

app.get('/sitemap.xml', async (_req, res) => {
  const urls = [`${PUBLIC_ORIGIN}/`];
  try {
    const response = await fetch(`${API}/api/users/events/?page_size=500`, {
      headers: { Accept: 'application/json' },
    });
    if (response.ok) {
      const payload = await response.json();
      const rows = Array.isArray(payload) ? payload : payload.results || [];
      for (const row of rows) {
        const key = (row.slug && String(row.slug).trim()) || row.id;
        if (key) urls.push(`${PUBLIC_ORIGIN}/event/${key}`);
      }
    }
  } catch (err) {
    console.warn('[seo-server] sitemap fetch failed:', err?.message || err);
  }
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (loc) => `  <url>
    <loc>${esc(loc)}</loc>
    <changefreq>daily</changefreq>
  </url>`
  )
  .join('\n')}
</urlset>
`;
  res.type('application/xml').set('Cache-Control', 'public, max-age=300').send(body);
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
  res.set('Cache-Control', 'public, max-age=60, stale-while-revalidate=300');
  res.type('html').send(html);
});

app.use(express.static(DIST, { index: false, maxAge: '1h' }));

app.get('*', (_req, res) => {
  res.type('html').send(readIndex());
});

app.listen(PORT, () => {
  console.log(`[seo-server] listening on :${PORT} api=${API}`);
});
