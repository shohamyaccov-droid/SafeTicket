function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function buildHowToJsonLd(page = {}) {
  const sections = page.sections || [];
  const sell = sections.find((s) => s.id === 'sell');
  const buy = sections.find((s) => s.id === 'buy');
  const toSteps = (section) =>
    (section?.items || []).map((item, index) => ({
      '@type': 'HowToStep',
      position: index + 1,
      name: String(item.strong || '').replace(/:$/, ''),
      text: `${item.strong || ''} ${item.text || ''}`.trim(),
    }));

  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'HowTo',
        name: 'איך למכור כרטיס להופעה ב-TradeTix',
        description: sell?.lead || page.description,
        step: toSteps(sell),
      },
      {
        '@type': 'HowTo',
        name: 'איך לקנות כרטיסים יד שניה ב-TradeTix',
        description: buy?.lead || page.description,
        step: toSteps(buy),
      },
    ],
  };
}

export function buildHowItWorksCrawlerHtml(page) {
  const sections = (page.sections || [])
    .map((section) => {
      const listTag = section.list === 'ul' ? 'ul' : 'ol';
      const items = (section.items || [])
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.strong)}</strong> ${escapeHtml(item.text)}</li>`,
        )
        .join('');
      const lead = section.lead ? `<p>${escapeHtml(section.lead)}</p>` : '';
      return `<section><h2>${escapeHtml(section.h2)}</h2>${lead}<${listTag}>${items}</${listTag}></section>`;
    })
    .join('');
  return (
    `<article class="seo-crawler-snapshot">` +
    `<h1>${escapeHtml(page.h1)}</h1>` +
    `<p>${escapeHtml(page.intro)}</p>` +
    sections +
    `</article>`
  );
}
