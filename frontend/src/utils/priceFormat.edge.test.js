/**
 * Extreme / hostile inputs for client pricing helpers.
 * Reflection: NaN, Infinity, negative fees, huge bases, wrong types.
 */
import { describe, expect, it } from 'vitest';
import {
  buyerChargeFromBase,
  buyerChargeFromBaseWithAffiliateCoupon,
  buyerChargeFromBaseWithFixedCoupon,
  formatAmountForCurrency,
  getTicketBaseNumeric,
  iso4217FromCountry,
} from './priceFormat.js';

describe('buyerChargeFromBase edge cases', () => {
  it.each([null, undefined, '', 'abc', NaN, Infinity, -Infinity, -1, 0, -100.5])(
    'returns zeros for invalid/non-positive base %s',
    (input) => {
      const r = buyerChargeFromBase(input);
      expect(r).toEqual({ baseAmount: 0, serviceFee: 0, totalAmount: 0 });
    },
  );

  it('accepts dynamic fee percent override', () => {
    const r = buyerChargeFromBase(100, 7);
    expect(r.serviceFee).toBe(7);
    expect(r.totalAmount).toBe(107);
  });

  it('falls back when fee percent is NaN', () => {
    const r = buyerChargeFromBase(100, NaN);
    expect(r.totalAmount).toBe(107);
  });

  it('never produces negative total with extreme fixed coupon', () => {
    const r = buyerChargeFromBaseWithFixedCoupon(1, 1e9);
    expect(r.totalAmount).toBe(0);
    expect(r.totalAmount).toBeGreaterThanOrEqual(0);
  });

  it('affiliate coupon on tiny base stays non-negative', () => {
    const r = buyerChargeFromBaseWithAffiliateCoupon(0.01);
    expect(r.totalAmount).toBeGreaterThanOrEqual(0);
    expect(r.serviceFee).toBeGreaterThanOrEqual(0);
  });
});

describe('formatAmountForCurrency edge cases', () => {
  it('handles non-numeric as zero', () => {
    expect(formatAmountForCurrency('nope', 'ILS')).toBe('0');
    expect(formatAmountForCurrency(undefined, 'USD')).toBe('0.00');
  });

  it('maps countries to ISO currencies safely', () => {
    expect(iso4217FromCountry('IL')).toBe('ILS');
    expect(iso4217FromCountry('US')).toBe('USD');
    expect(iso4217FromCountry(null)).toBe('ILS');
    expect(iso4217FromCountry('ZZ')).toBe('ILS');
  });

  it('getTicketBaseNumeric rejects garbage', () => {
    expect(getTicketBaseNumeric(null)).toBe(0);
    expect(getTicketBaseNumeric({ asking_price: 'x' })).toBe(0);
    expect(getTicketBaseNumeric({ asking_price: '-5' })).toBe(-5);
  });
});
