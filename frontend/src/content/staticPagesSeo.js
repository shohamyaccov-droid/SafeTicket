import { createRequire } from 'module';
import { DEFAULT_SITE_DESCRIPTION, DEFAULT_SITE_TITLE } from '../utils/siteSeo.js';
import { buildHowItWorksCrawlerHtml, buildHowToJsonLd } from './howItWorksRender.js';

const require = createRequire(import.meta.url);
const howItWorks = require('./how-it-works.json');
const howToSell = require('./how-to-sell.json');
const faqCrawler = require('./faq-crawler.json');

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
    `</article>`
  );
}

export function getStaticPageSeo(pathname, origin) {
  const path = pathname === '' ? '/' : pathname.startsWith('/') ? pathname : `/${pathname}`;
  const base = String(origin || 'https://tradetix.co.il').replace(/\/$/, '');
  if (path === '/how-it-works') {
    return {
      seo_title: howItWorks.h1,
      seo_description: howItWorks.description,
      canonical_url: `${base}/how-it-works`,
      og_image: `${base}/og-share.png`,
      json_ld: buildHowToJsonLd(howItWorks),
      crawler_html: buildHowItWorksCrawlerHtml(howItWorks),
    };
  }
  if (path === '/how-to-sell') {
    return {
      seo_title: howToSell.title,
      seo_description: howToSell.description,
      canonical_url: `${base}/how-to-sell`,
      og_image: `${base}/og-share.png`,
      json_ld: buildHowToSellFaqJsonLd(howToSell),
      crawler_html: buildHowToSellCrawlerHtml(howToSell),
    };
  }
  if (path === '/faq') {
    return {
      seo_title: faqCrawler.title,
      seo_description: faqCrawler.description,
      canonical_url: `${base}/faq`,
      og_image: `${base}/og-share.png`,
      json_ld: buildFaqJsonLd(faqCrawler),
      crawler_html: buildFaqCrawlerHtml(faqCrawler),
    };
  }
  if (path === '/') {
    return {
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
    };
  }
  return null;
}
