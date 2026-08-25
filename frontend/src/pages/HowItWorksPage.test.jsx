import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { describe, expect, it } from 'vitest';
import HowItWorksPage from './HowItWorksPage';

describe('HowItWorksPage', () => {
  it('renders semantic headings, numbered steps, and target keywords', () => {
    const { container } = render(
      <HelmetProvider>
        <MemoryRouter>
          <HowItWorksPage />
        </MemoryRouter>
      </HelmetProvider>,
    );
    expect(
      screen.getByRole('heading', {
        level: 1,
        name: 'איך זה עובד? המדריך המלא לקנייה ומכירת כרטיסים ב-TradeTix',
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        level: 2,
        name: 'נתקעתם עם כרטיס? איך למכור כרטיס להופעה ב-3 צעדים פשוטים',
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        level: 2,
        name: 'איך לקנות כרטיסים יד שניה בראש שקט?',
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'למה לבחור ב-TradeTix?' })).toBeInTheDocument();
    expect(container.querySelectorAll('ol').length).toBeGreaterThanOrEqual(2);
    expect(container.querySelectorAll('ul').length).toBeGreaterThanOrEqual(1);
    expect(container.textContent).toContain('איך למכור כרטיס');
    expect(container.textContent).toContain('כרטיסים יד שניה');
    expect(container.textContent).toContain('תשלום מאובטח');
  });
});
