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
    render(
      <ListingCreatedSuccessView
        successWasIsrael={false}
        onAddPayoutDetails={() => {}}
        onDoLater={() => {}}
      />,
    );

    expect(screen.getByTestId('listing-success')).toBeInTheDocument();
    expect(screen.getByText('הכרטיס פורסם בהצלחה!')).toBeInTheDocument();
    expect(screen.getByTestId('listing-success-payout-copy')).toHaveTextContent('לא גובים');
    expect(window.gtag).toHaveBeenCalledTimes(1);
    expect(window.gtag).toHaveBeenCalledWith('event', 'conversion', {
      send_to: 'AW-18350905085/QVV8COaZ0tYcEP2tsq5E',
    });
  });

  it('does not fire again on rerender of the same mounted success view', () => {
    const { rerender } = render(
      <ListingCreatedSuccessView
        successWasIsrael={false}
        onAddPayoutDetails={() => {}}
        onDoLater={() => {}}
      />,
    );
    rerender(
      <ListingCreatedSuccessView
        successWasIsrael
        onAddPayoutDetails={() => {}}
        onDoLater={() => {}}
      />,
    );
    expect(window.gtag).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/בדיקת צוות/)).toBeInTheDocument();
  });

  it('skips gtag when it is not loaded', () => {
    delete window.gtag;
    expect(() =>
      render(
        <ListingCreatedSuccessView
          successWasIsrael={false}
          onAddPayoutDetails={() => {}}
          onDoLater={() => {}}
        />,
      ),
    ).not.toThrow();
  });

  it('routes payout now vs later from the two CTAs', async () => {
    const onAddPayoutDetails = vi.fn();
    const onDoLater = vi.fn();
    const user = userEvent.setup();
    render(
      <ListingCreatedSuccessView
        successWasIsrael={false}
        onAddPayoutDetails={onAddPayoutDetails}
        onDoLater={onDoLater}
      />,
    );
    await user.click(screen.getByRole('button', { name: 'הוספת פרטי תשלום עכשיו' }));
    expect(onAddPayoutDetails).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole('button', { name: 'אעשה את זה אחר כך' }));
    expect(onDoLater).toHaveBeenCalledTimes(1);
  });
});
