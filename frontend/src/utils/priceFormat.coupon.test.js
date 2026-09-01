/**
 * Pure pricing math for affiliate coupon + 7% base fee (GlobalFeeSettings defaults).
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
  buyerChargeFromBaseWithFixedCoupon,
} from './priceFormat.js';

describe('buyerChargeFromBase (7% fee)', () => {
  it('charges exactly 7% on 100', () => {
    expect(BUYER_SERVICE_FEE_PERCENT).toBe(7);
    const r = buyerChargeFromBase(100);
    expect(r.baseAmount).toBe(100);
    expect(r.serviceFee).toBe(7);
    expect(r.totalAmount).toBe(107);
  });

  it('charges exactly 7% on 300 so listings can show ₪321', () => {
    const r = buyerChargeFromBase(300);
    expect(r.baseAmount).toBe(300);
    expect(r.serviceFee).toBe(21);
    expect(r.totalAmount).toBe(321);
  });
});

describe('buyerChargeFromBaseWithFixedCoupon', () => {
  it('subtracts a fixed amount from the normal checkout total without shrinking the 7% fee line', () => {
    const r = buyerChargeFromBaseWithFixedCoupon(498, 20);
    expect(r.baseAmount).toBe(498);
    expect(r.serviceFee).toBe(34.86);
    expect(r.buyerDiscount).toBe(20);
    expect(r.totalAmount).toBe(512.86);
    expect(Number((r.baseAmount + r.serviceFee - r.buyerDiscount).toFixed(2))).toBe(r.totalAmount);
  });

  it('keeps the full 7% service fee when a ₪20 coupon is applied to ₪100', () => {
    const r = buyerChargeFromBaseWithFixedCoupon(100, 20);
    expect(r.baseAmount).toBe(100);
    expect(r.serviceFee).toBe(7);
    expect(r.buyerDiscount).toBe(20);
    expect(r.totalAmount).toBe(87);
  });

  it('never produces a negative total', () => {
    const r = buyerChargeFromBaseWithFixedCoupon(5, 20);
    expect(r.buyerDiscount).toBe(5.35);
    expect(r.totalAmount).toBe(0);
  });
});

describe('buyerChargeFromBaseWithAffiliateCoupon', () => {
  it('splits 7% into 5/2/0 and charges buyer 2%', () => {
    expect(BUYER_FEE_PERCENT_WITH_COUPON).toBe(2);
    expect(AFFILIATE_BUYER_DISCOUNT_PERCENT).toBe(5);
    expect(AFFILIATE_COMMISSION_PERCENT).toBe(2);
    expect(AFFILIATE_PLATFORM_NET_PERCENT).toBe(0);
    const r = buyerChargeFromBaseWithAffiliateCoupon(100);
    expect(r.baseAmount).toBe(100);
    expect(r.serviceFee).toBe(2);
    expect(r.buyerDiscount).toBe(5);
    expect(r.affiliateCommission).toBe(2);
    expect(r.platformNetFee).toBe(0);
    expect(r.totalAmount).toBe(102);
  });

  it('handles multi-ticket subtotal precisely', () => {
    const r = buyerChargeFromBaseWithAffiliateCoupon(300);
    expect(r.serviceFee).toBe(6);
    expect(r.buyerDiscount).toBe(15);
    expect(r.affiliateCommission).toBe(6);
    expect(r.platformNetFee).toBe(0);
    expect(r.totalAmount).toBe(306);
  });
});
