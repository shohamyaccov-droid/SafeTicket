import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { afterEach, describe, expect, it } from 'vitest';
import HowToSellPage from './HowToSellPage';
import { buildHowToSellFaqJsonLd } from '../content/howToSellContent';

afterEach(() => {
  cleanup();
  document.body.classList.remove('has-how-to-sell-cta');
});

function renderPage() {
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <HowToSellPage />
      </MemoryRouter>
    </HelmetProvider>,
  );
}

describe('HowToSellPage', () => {
  it('uses the exact-match H1, numbered steps, and FAQ copy', () => {
    const { container } = renderPage();
    expect(container.querySelector('article')).toBeTruthy();
    expect(container.querySelectorAll('section').length).toBeGreaterThanOrEqual(4);
    expect(
      screen.getByRole('heading', { level: 1, name: 'איך למכור כרטיס להופעה' }),
    ).toBeInTheDocument();
    expect(container.querySelectorAll('h1')).toHaveLength(1);
    expect(container.querySelector('ol')).toBeTruthy();
    expect(container.querySelectorAll('ol li')).toHaveLength(3);
    expect(container.textContent).toContain('העלאת הכרטיס');
    expect(container.textContent).toContain('אימות טלפוני');
    expect(container.textContent).toContain('קבלת התשלום');
    expect(
      screen.getByRole('heading', { level: 2, name: 'איך למכור כרטיס להופעה בצורה בטוחה?' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: 'כמה עולה למכור כרטיס להופעה יד שנייה?' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: 'איך נמנעים מנוכלים במכירת כרטיסים?' }),
    ).toBeInTheDocument();
  });

  it('keeps the sticky CTA pointed at the sell wizard', () => {
    renderPage();
    const ctas = screen.getAllByRole('link', { name: 'מכירת כרטיס עכשיו' });
    expect(ctas.length).toBeGreaterThanOrEqual(2);
    ctas.forEach((cta) => expect(cta).toHaveAttribute('href', '/sell/new'));
  });

  it('builds FAQPage JSON-LD with the three Hebrew Q&As', () => {
    const jsonLd = buildHowToSellFaqJsonLd();
    expect(jsonLd['@type']).toBe('FAQPage');
    expect(jsonLd.mainEntity).toHaveLength(3);
    expect(jsonLd.mainEntity[0].name).toBe('איך למכור כרטיס להופעה בצורה בטוחה?');
    expect(jsonLd.mainEntity[1].acceptedAnswer.text).toContain('0% עמלה למוכרים');
    expect(jsonLd.mainEntity[2].acceptedAnswer.text).toContain('אימות מספר טלפון');
  });
});
