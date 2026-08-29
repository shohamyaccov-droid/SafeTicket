import howToSell from './how-to-sell.json';

export const HOW_TO_SELL = howToSell;

export function buildHowToSellFaqJsonLd(page = HOW_TO_SELL) {
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

export function buildHowToSellHowToJsonLd(page = HOW_TO_SELL) {
  return {
    '@context': 'https://schema.org',
    '@type': 'HowTo',
    name: page.h1,
    description: page.description,
    step: (page.steps || []).map((step, index) => ({
      '@type': 'HowToStep',
      position: index + 1,
      name: step.name,
      text: `${step.name}: ${step.text}`,
    })),
  };
}

export function buildHowToSellCrawlerHtml(page = HOW_TO_SELL) {
  const escape = (value) =>
    String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  const steps = (page.steps || [])
    .map((step) => `<li><strong>${escape(step.name)}</strong> ${escape(step.text)}</li>`)
    .join('');
  const faqs = (page.faqs || [])
    .map(
      (item) =>
        `<section><h2>${escape(item.question)}</h2><p>${escape(item.answer)}</p></section>`,
    )
    .join('');
  return (
    `<article class="seo-crawler-snapshot">` +
    `<h1>${escape(page.h1)}</h1>` +
    `<p>${escape(page.intro)}</p>` +
    `<section><h2>${escape(page.steps_h2)}</h2>` +
    `<p>${escape(page.steps_lead)}</p>` +
    `<ol>${steps}</ol></section>` +
    faqs +
    `</article>`
  );
}
