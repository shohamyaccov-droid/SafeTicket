/** Must match backend GlobalFeeSettings defaults (7% buyer fee; sellers 0%).
 * Live checkout / listings load current values from GET /users/pricing/settings/.
 */

export const BUYER_SERVICE_FEE_PERCENT = 7;
/** Coupon splits: buyer discount 5% + affiliate 2% + platform remainder 0% (= 7%). */
export const AFFILIATE_BUYER_DISCOUNT_PERCENT = 5;
export const AFFILIATE_COMMISSION_PERCENT = 2;
export const AFFILIATE_PLATFORM_NET_PERCENT = 0;

export const BUYER_FEE_PERCENT_WITH_COUPON =
  BUYER_SERVICE_FEE_PERCENT - AFFILIATE_BUYER_DISCOUNT_PERCENT;
