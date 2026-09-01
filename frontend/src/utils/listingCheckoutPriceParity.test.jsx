import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import BuyerListingPrice from '../components/BuyerListingPrice';
import EventMobileBuyBar from '../components/EventMobileBuyBar';
import {
  buyerAllInFromTicket,
  buyerChargeFromBase,
  formatAmountForCurrency,
} from './priceFormat';

vi.mock('../hooks/useBuyerServiceFeePercent', () => ({
  default: () => 7,
}));

/**
 * CheckoutModal totals come from buyerChargeFromBase (see CheckoutModal.jsx).
 * Event listing surfaces must print that same totalAmount, with no fee copy.
 */
describe('event listing price matches checkout total', () => {
  it('charges ₪321 for a ₪300 face value (7%)', () => {
    const checkout = buyerChargeFromBase(300, 7);
    expect(checkout.baseAmount).toBe(300);
    expect(checkout.serviceFee).toBe(21);
    expect(checkout.totalAmount).toBe(321);
    expect(formatAmountForCurrency(checkout.totalAmount, 'ILS')).toBe('321');
  });

  it('BuyerListingPrice and EventMobileBuyBar show the checkout total, not the face value', () => {
    const ticket = { asking_price: '300.00', original_price: '300.00', currency: 'ILS' };
    const checkoutTotal = buyerChargeFromBase(300, 7).totalAmount;
    const listing = buyerAllInFromTicket(ticket, 7);

    expect(listing.totalAmount).toBe(checkoutTotal);
    expect(listing.formattedTotal).toBe('321');

    const fractional = buyerAllInFromTicket(
      { asking_price: '249.00', original_price: '249.00', currency: 'ILS' },
      7,
    );
    expect(fractional.totalAmount).toBe(266.43);
    expect(formatAmountForCurrency(fractional.totalAmount, 'ILS')).toBe('266.43');
    expect(fractional.formattedTotal).toBe('266');

    const { unmount } = render(<BuyerListingPrice ticket={ticket} />);
    expect(screen.getByText('₪321')).toBeInTheDocument();
    expect(screen.queryByText(/דמי שירות/)).not.toBeInTheDocument();
    expect(screen.queryByText(/לפני/)).not.toBeInTheDocument();
    unmount();

    render(<EventMobileBuyBar ticket={ticket} onBuy={() => {}} />);
    expect(screen.getByText('₪321')).toBeInTheDocument();
    expect(screen.queryByText(/דמי שירות/)).not.toBeInTheDocument();
  });

  it('rounds listing display to whole shekels without changing the checkout total', () => {
    const ticket = { asking_price: '249.00', original_price: '249.00', currency: 'ILS' };
    const listing = buyerAllInFromTicket(ticket, 7);
    expect(listing.totalAmount).toBe(266.43);
    expect(listing.formattedTotal).toBe('266');

    render(<BuyerListingPrice ticket={ticket} />);
    expect(screen.getByText('₪266')).toBeInTheDocument();
    expect(screen.queryByText(/266\.43/)).not.toBeInTheDocument();
  });
});
