import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { describe, expect, it } from 'vitest';
import HowItWorksPage from './HowItWorksPage';

describe('HowItWorksPage', () => {
  it('renders semantic headings for crawlers', () => {
    render(
      <HelmetProvider>
        <MemoryRouter>
          <HowItWorksPage />
        </MemoryRouter>
      </HelmetProvider>,
    );
    expect(screen.getByRole('heading', { level: 1, name: 'איך זה עובד' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'קנייה של כרטיס' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'מכירת כרטיס' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'הגנה על הכסף' })).toBeInTheDocument();
  });
});
