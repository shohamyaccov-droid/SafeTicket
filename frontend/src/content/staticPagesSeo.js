import { createRequire } from 'module';
import { DEFAULT_SITE_DESCRIPTION, DEFAULT_SITE_TITLE } from '../utils/siteSeo.js';
import { buildHowItWorksCrawlerHtml, buildHowToJsonLd } from './howItWorksRender.js';

const require = createRequire(import.meta.url);
const howItWorks = require('./how-it-works.json');
const howToSell = require('./how-to-sell.json');
const faqCrawler = require('./faq-crawler.json');
const staticPageMeta = require('./static-page-meta.json');

function breadcrumbJsonLd(origin, route, name) {
  const items = [{ name: 'דף הבית', path: '/' }];
  if (route !== '/') items.push({ name, path: route });
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.path === '/' ? `${origin}/` : `${origin}${item.path}`,
    })),
  };
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function buildFaqCrawlerHtml(page = faqCrawler) {
  const items = (page.items || [])
    .map(
      (item) =>
        `<section><h2>${escapeHtml(item.question)}</h2><p>${escapeHtml(item.answer)}</p></section>`,
    )
    .join('');
  return (
    `<article class="seo-crawler-snapshot">` +
    `<h1>${escapeHtml(page.h1)}</h1>` +
    `<p>${escapeHtml(page.intro)}</p>` +
    items +
    `</article>`
  );
}

function buildHowToSellFaqJsonLd(page = howToSell) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: (page.faqs || []).map((item) => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: { '@type': 'Answer', text: item.answer },
    })),
  };
}

function buildHowToSellCrawlerHtml(page = howToSell) {
  const steps = (page.steps || [])
    .map((step) => `<li><strong>${escapeHtml(step.name)}</strong> ${escapeHtml(step.text)}</li>`)
    .join('');
  const faqs = (page.faqs || [])
    .map(
      (item) =>
        `<section><h2>${escapeHtml(item.question)}</h2><p>${escapeHtml(item.answer)}</p></section>`,
    )
    .join('');
  return (
    `<article class="seo-crawler-snapshot">` +
    `<h1>${escapeHtml(page.h1)}</h1>` +
    `<p>${escapeHtml(page.intro)}</p>` +
    `<section><h2>${escapeHtml(page.steps_h2)}</h2>` +
    `<p>${escapeHtml(page.steps_lead)}</p>` +
    `<ol>${steps}</ol></section>` +
    faqs +
    `</article>`
  );
}

function buildFaqJsonLd(page = faqCrawler) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: (page.items || []).map((item) => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: { '@type': 'Answer', text: item.answer },
    })),
  };
}

function buildHomeCrawlerHtml() {
  return (
    `<article class="seo-crawler-snapshot">` +
    `<h1>${escapeHtml(DEFAULT_SITE_TITLE)}</h1>` +
    `<p>${escapeHtml(DEFAULT_SITE_DESCRIPTION)}</p>` +
    `<p>TradeTix היא זירת מסחר בטוחה לכרטיסים יד שנייה בישראל. קנייה ומכירה עם תשלום מאובטח והגנה על הכסף.</p>` +
    `<ol><li>חיפוש</li><li>אימות</li><li>כניסה</li></ol>` +
    `</article>`
  );
}

function withBreadcrumb(payload, origin, path, name) {
  return { ...payload, breadcrumb_json_ld: breadcrumbJsonLd(origin, path, name) };
}

export function getStaticPageSeo(pathname, origin) {
  const path = pathname === '' ? '/' : pathname.startsWith('/') ? pathname : `/${pathname}`;
  const base = String(origin || 'https://tradetix.co.il').replace(/\/$/, '');
  if (path === '/how-it-works') {
    return withBreadcrumb(
      {
        seo_title: howItWorks.h1,
        seo_description: howItWorks.description,
        canonical_url: `${base}/how-it-works`,
        og_image: `${base}/og-share.png`,
        json_ld: buildHowToJsonLd(howItWorks),
        extra_json_ld: [buildHowToSellFaqJsonLd(howToSell)],
        crawler_html: buildHowItWorksCrawlerHtml(howItWorks),
      },
      base,
      path,
      'איך זה עובד',
    );
  }
  if (path === '/how-to-sell') {
    return withBreadcrumb(
      {
        seo_title: howToSell.title,
        seo_description: howToSell.description,
        canonical_url: `${base}/how-to-sell`,
        og_image: `${base}/og-share.png`,
        json_ld: buildHowToSellFaqJsonLd(howToSell),
        crawler_html: buildHowToSellCrawlerHtml(howToSell),
      },
      base,
      path,
      'איך למכור כרטיס',
    );
  }
  if (path === '/faq') {
    return withBreadcrumb(
      {
        seo_title: faqCrawler.title,
        seo_description: faqCrawler.description,
        canonical_url: `${base}/faq`,
        og_image: `${base}/og-share.png`,
        json_ld: buildFaqJsonLd(faqCrawler),
        crawler_html: buildFaqCrawlerHtml(faqCrawler),
      },
      base,
      path,
      'שאלות ותשובות',
    );
  }
  if (path === '/') {
    return withBreadcrumb(
      {
        seo_title: DEFAULT_SITE_TITLE,
        seo_description: DEFAULT_SITE_DESCRIPTION,
        canonical_url: `${base}/`,
        og_image: `${base}/og-share.png`,
        json_ld: {
          '@context': 'https://schema.org',
          '@type': 'WebSite',
          name: 'TradeTix',
          url: `${base}/`,
          description: DEFAULT_SITE_DESCRIPTION,
          inLanguage: 'he-IL',
        },
        crawler_html: buildHomeCrawlerHtml(),
      },
      base,
      path,
      'דף הבית',
    );
  }
  if (path === '/sell/new') {
    const meta = staticPageMeta[path] || {};
    const steps = (howToSell.steps || [])
      .map((step) => `<li><strong>${escapeHtml(step.name)}</strong> ${escapeHtml(step.text)}</li>`)
      .join('');
    const faqs = (howToSell.faqs || [])
      .map(
        (item) =>
          `<section><h2>${escapeHtml(item.question)}</h2><p>${escapeHtml(item.answer)}</p></section>`,
      )
      .join('');
    return withBreadcrumb(
      {
        seo_title: meta.title || 'מכירת כרטיס להופעה ב-0% עמלה | TradeTix',
        seo_description: meta.description || howToSell.description,
        canonical_url: `${base}/sell/new`,
        og_image: `${base}/og-share.png`,
        json_ld: buildHowToSellFaqJsonLd(howToSell),
        crawler_html:
          `<article class="seo-crawler-snapshot">` +
          `<h1>מכירת כרטיס ב-TradeTix</h1>` +
          `<p>0% עמלה למוכרים, אימות טלפון חובה, והכסף נשמר בנאמנות SafePay עד לאחר ההופעה.</p>` +
          `<section><h2>איך למכור כרטיס ב-3 צעדים</h2><ol>${steps}</ol></section>` +
          faqs +
          `</article>`,
      },
      base,
      path,
      'מכירת כרטיס',
    );
  }
  const meta = staticPageMeta[path];
  if (meta) {
    return withBreadcrumb(
      {
        seo_title: meta.title,
        seo_description: meta.description,
        canonical_url: `${base}${path}`,
        og_image: `${base}/og-share.png`,
        json_ld: {
          '@context': 'https://schema.org',
          '@type': 'WebPage',
          name: meta.title,
          url: `${base}${path}`,
          description: meta.description,
          inLanguage: 'he-IL',
        },
        crawler_html:
          `<article class="seo-crawler-snapshot">` +
          `<h1>${escapeHtml(meta.title)}</h1>` +
          `<p>${escapeHtml(meta.description)}</p>` +
          `</article>`,
      },
      base,
      path,
      meta.title.split('|')[0].trim(),
    );
  }
  return null;
}
