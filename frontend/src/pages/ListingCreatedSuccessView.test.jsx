import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import ListingCreatedSuccessView from './ListingCreatedSuccessView';

describe('ListingCreatedSuccessView Google Ads conversion', () => {
  beforeEach(() => {
    window.gtag = vi.fn();
  });

  afterEach(() => {
    cleanup();
    delete window.gtag;
  });

  it('fires the conversion exactly once when the success view mounts', () => {
    render(<ListingCreatedSuccessView successWasIsrael={false} onGoToSales={() => {}} />);

    expect(screen.getByTestId('listing-success')).toBeInTheDocument();
    expect(screen.getByText('הכרטיס הועלה בהצלחה!')).toBeInTheDocument();
    expect(window.gtag).toHaveBeenCalledTimes(1);
    expect(window.gtag).toHaveBeenCalledWith('event', 'conversion', {
      send_to: 'AW-18350905085/QVV8COaZ0tYcEP2tsq5E',
    });
  });

  it('does not fire again on rerender of the same mounted success view', () => {
    const { rerender } = render(
      <ListingCreatedSuccessView successWasIsrael={false} onGoToSales={() => {}} />,
    );
    rerender(<ListingCreatedSuccessView successWasIsrael onGoToSales={() => {}} />);
    expect(window.gtag).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/בדיקת צוות/)).toBeInTheDocument();
  });

  it('skips gtag when it is not loaded', () => {
    delete window.gtag;
    expect(() =>
      render(<ListingCreatedSuccessView successWasIsrael={false} onGoToSales={() => {}} />),
    ).not.toThrow();
  });

  it('calls onGoToSales from the CTA', async () => {
    const onGoToSales = vi.fn();
    const user = userEvent.setup();
    render(<ListingCreatedSuccessView successWasIsrael={false} onGoToSales={onGoToSales} />);
    await user.click(screen.getByRole('button', { name: 'למכירות שלי' }));
    expect(onGoToSales).toHaveBeenCalledTimes(1);
  });
});
