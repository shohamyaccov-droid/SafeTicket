/**
 * Pure pricing math for affiliate coupon + 15% base fee.
 * Run: npm test (vitest)
 */
import { describe, expect, it } from 'vitest';
import {
  AFFILIATE_BUYER_DISCOUNT_PERCENT,
  BUYER_FEE_PERCENT_WITH_COUPON,
  BUYER_SERVICE_FEE_PERCENT,
} from '../constants/pricing.js';
import {
  buyerChargeFromBase,
  buyerChargeFromBaseWithAffiliateCoupon,
} from './priceFormat.js';

describe('buyerChargeFromBase (15% fee)', () => {
  it('charges exactly 15% on 100', () => {
    expect(BUYER_SERVICE_FEE_PERCENT).toBe(15);
    const r = buyerChargeFromBase(100);
    expect(r.baseAmount).toBe(100);
    expect(r.serviceFee).toBe(15);
    expect(r.totalAmount).toBe(115);
  });
});

describe('buyerChargeFromBaseWithAffiliateCoupon', () => {
  it('splits 15% into 5/5/5 and charges buyer 10%', () => {
    expect(BUYER_FEE_PERCENT_WITH_COUPON).toBe(10);
    expect(AFFILIATE_BUYER_DISCOUNT_PERCENT).toBe(5);
    const r = buyerChargeFromBaseWithAffiliateCoupon(100);
    expect(r.baseAmount).toBe(100);
    expect(r.serviceFee).toBe(10);
    expect(r.buyerDiscount).toBe(5);
    expect(r.affiliateCommission).toBe(5);
    expect(r.platformNetFee).toBe(5);
    expect(r.totalAmount).toBe(110);
  });

  it('handles multi-ticket subtotal precisely', () => {
    const r = buyerChargeFromBaseWithAffiliateCoupon(300);
    expect(r.serviceFee).toBe(30);
    expect(r.buyerDiscount).toBe(15);
    expect(r.totalAmount).toBe(330);
  });
});
