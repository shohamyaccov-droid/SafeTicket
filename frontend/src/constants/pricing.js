/** Must match backend GlobalFeeSettings defaults (12% buyer fee; sellers 0%). */

export const BUYER_SERVICE_FEE_PERCENT = 12;

/** Coupon splits: buyer discount 5% + affiliate 5% + platform remainder 2% (= 12%). */
export const AFFILIATE_BUYER_DISCOUNT_PERCENT = 5;
export const AFFILIATE_COMMISSION_PERCENT = 5;
export const AFFILIATE_PLATFORM_NET_PERCENT = 2;

export const BUYER_FEE_PERCENT_WITH_COUPON =
  BUYER_SERVICE_FEE_PERCENT - AFFILIATE_BUYER_DISCOUNT_PERCENT;
