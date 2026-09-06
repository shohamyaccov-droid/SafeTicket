import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import BuyerListingPrice from '../components/BuyerListingPrice';
import EventMobileBuyBar from '../components/EventMobileBuyBar';
import {
  buyerChargeFromBase,
  formatAmountForCurrency,
  formatListingAmountForCurrency,
  getTicketBaseNumeric,
} from './priceFormat';

/**
 * Listing surfaces show face value only. CheckoutModal adds the 7% platform fee.
 */
describe('event listing shows base price; checkout adds fee', () => {
  it('charges ₪321 at checkout for a ₪300 face value (7%)', () => {
    const checkout = buyerChargeFromBase(300, 7);
    expect(checkout.baseAmount).toBe(300);
    expect(checkout.serviceFee).toBe(21);
    expect(checkout.totalAmount).toBe(321);
    expect(formatAmountForCurrency(checkout.totalAmount, 'ILS')).toBe('321');
  });

  it('BuyerListingPrice and EventMobileBuyBar show face value, not the checkout total', () => {
    const ticket = { asking_price: '300.00', original_price: '300.00', currency: 'ILS' };
    expect(getTicketBaseNumeric(ticket)).toBe(300);
    expect(formatListingAmountForCurrency(300, 'ILS')).toBe('300');

    const { unmount } = render(<BuyerListingPrice ticket={ticket} />);
    expect(screen.getByText('₪300')).toBeInTheDocument();
    expect(screen.queryByText('₪321')).not.toBeInTheDocument();
    expect(screen.queryByText(/דמי שירות|דמי פלטפורמה/)).not.toBeInTheDocument();
    unmount();

    render(<EventMobileBuyBar ticket={ticket} onBuy={() => {}} />);
    expect(screen.getByText('₪300')).toBeInTheDocument();
    expect(screen.queryByText('₪321')).not.toBeInTheDocument();
    expect(screen.queryByText(/דמי שירות|דמי פלטפורמה/)).not.toBeInTheDocument();
  });

  it('rounds listing display to whole shekels on the face value', () => {
    const ticket = { asking_price: '249.00', original_price: '249.00', currency: 'ILS' };
    expect(buyerChargeFromBase(249, 7).totalAmount).toBe(266.43);

    render(<BuyerListingPrice ticket={ticket} />);
    expect(screen.getByText('₪249')).toBeInTheDocument();
    expect(screen.queryByText('₪266')).not.toBeInTheDocument();
    expect(screen.queryByText(/266\.43/)).not.toBeInTheDocument();
  });
});
