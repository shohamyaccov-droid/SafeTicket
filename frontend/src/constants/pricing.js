/** Must match backend PLATFORM_BUYER_SERVICE_FEE_RATE (default 0.15). Sellers pay 0%. */
export const BUYER_SERVICE_FEE_PERCENT = 15;

/** Affiliate coupon splits the 15% fee into: 5% buyer discount + 5% affiliate + 5% platform. */
export const AFFILIATE_BUYER_DISCOUNT_PERCENT = 5;
export const AFFILIATE_COMMISSION_PERCENT = 5;
export const AFFILIATE_PLATFORM_NET_PERCENT = 5;
export const BUYER_FEE_PERCENT_WITH_COUPON = BUYER_SERVICE_FEE_PERCENT - AFFILIATE_BUYER_DISCOUNT_PERCENT;
