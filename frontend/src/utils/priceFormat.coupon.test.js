/**
 * Pure pricing math for affiliate coupon + 12% base fee (GlobalFeeSettings defaults).
 * Run: npm test (vitest)
 */
import { describe, expect, it } from 'vitest';
import {
  AFFILIATE_BUYER_DISCOUNT_PERCENT,
  AFFILIATE_COMMISSION_PERCENT,
  AFFILIATE_PLATFORM_NET_PERCENT,
  BUYER_FEE_PERCENT_WITH_COUPON,
  BUYER_SERVICE_FEE_PERCENT,
} from '../constants/pricing.js';
import {
  buyerChargeFromBase,
  buyerChargeFromBaseWithAffiliateCoupon,
} from './priceFormat.js';

describe('buyerChargeFromBase (12% fee)', () => {
  it('charges exactly 12% on 100', () => {
    expect(BUYER_SERVICE_FEE_PERCENT).toBe(12);
    const r = buyerChargeFromBase(100);
    expect(r.baseAmount).toBe(100);
    expect(r.serviceFee).toBe(12);
    expect(r.totalAmount).toBe(112);
  });
});

describe('buyerChargeFromBaseWithAffiliateCoupon', () => {
  it('splits 12% into 5/5/2 and charges buyer 7%', () => {
    expect(BUYER_FEE_PERCENT_WITH_COUPON).toBe(7);
    expect(AFFILIATE_BUYER_DISCOUNT_PERCENT).toBe(5);
    expect(AFFILIATE_COMMISSION_PERCENT).toBe(5);
    expect(AFFILIATE_PLATFORM_NET_PERCENT).toBe(2);
    const r = buyerChargeFromBaseWithAffiliateCoupon(100);
    expect(r.baseAmount).toBe(100);
    expect(r.serviceFee).toBe(7);
    expect(r.buyerDiscount).toBe(5);
    expect(r.affiliateCommission).toBe(5);
    expect(r.platformNetFee).toBe(2);
    expect(r.totalAmount).toBe(107);
  });

  it('handles multi-ticket subtotal precisely', () => {
    const r = buyerChargeFromBaseWithAffiliateCoupon(300);
    expect(r.serviceFee).toBe(21);
    expect(r.buyerDiscount).toBe(15);
    expect(r.affiliateCommission).toBe(15);
    expect(r.platformNetFee).toBe(6);
    expect(r.totalAmount).toBe(321);
  });
});
