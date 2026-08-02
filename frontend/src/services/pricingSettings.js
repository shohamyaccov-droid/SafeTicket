/**
 * Shared live pricing settings from GET /users/pricing/settings/
 * (GlobalFeeSettings). One in-flight request; all hooks subscribe to the same cache.
 */
import { orderAPI } from './api';
import {
  AFFILIATE_BUYER_DISCOUNT_PERCENT,
  AFFILIATE_COMMISSION_PERCENT,
  AFFILIATE_PLATFORM_NET_PERCENT,
  BUYER_FEE_PERCENT_WITH_COUPON,
  BUYER_SERVICE_FEE_PERCENT,
} from '../constants/pricing';

const FALLBACK = Object.freeze({
  serviceFeePercent: BUYER_SERVICE_FEE_PERCENT,
  feeWithCouponPercent: BUYER_FEE_PERCENT_WITH_COUPON,
  discountPercent: AFFILIATE_BUYER_DISCOUNT_PERCENT,
  affiliatePercent: AFFILIATE_COMMISSION_PERCENT,
  platformNetPercent: AFFILIATE_PLATFORM_NET_PERCENT,
});

let cache = null;
let inflight = null;
const listeners = new Set();

function parsePercent(raw, fallback) {
  const next = parseFloat(raw);
  return Number.isFinite(next) && next >= 0 ? next : fallback;
}

/** Strip trailing zeros for display (7.00 → "7", 7.50 → "7.5"). */
export function formatBuyerFeePercent(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return String(BUYER_SERVICE_FEE_PERCENT);
  return String(parseFloat(n.toFixed(2)));
}

export function getCachedPricingSettings() {
  return cache || FALLBACK;
}

export function getCachedBuyerFeePercent() {
  return getCachedPricingSettings().serviceFeePercent;
}

function notify(next) {
  listeners.forEach((listener) => {
    try {
      listener(next);
    } catch {
      /* ignore subscriber errors */
    }
  });
}

export function subscribePricingSettings(listener) {
  listeners.add(listener);
  if (cache) listener(cache);
  return () => listeners.delete(listener);
}

/**
 * Load (or reuse) platform fee settings. Pass `{ force: true }` to refresh after
 * admin changes (also triggered on window focus from the hook bootstrap).
 */
export function loadPricingSettings({ force = false } = {}) {
  if (!force && cache) return Promise.resolve(cache);
  if (!force && inflight) return inflight;

  inflight = orderAPI
    .getPricingSettings()
    .then((res) => {
      const data = res?.data || {};
      const serviceFeePercent = parsePercent(
        data.service_fee_percentage ?? data.base_buyer_fee_percent,
        BUYER_SERVICE_FEE_PERCENT,
      );
      const discountPercent = parsePercent(
        data.buyer_coupon_discount_percent,
        AFFILIATE_BUYER_DISCOUNT_PERCENT,
      );
      const affiliatePercent = parsePercent(
        data.affiliate_commission_percent,
        AFFILIATE_COMMISSION_PERCENT,
      );
      const platformNetPercent = parsePercent(
        data.affiliate_platform_net_percent,
        AFFILIATE_PLATFORM_NET_PERCENT,
      );
      const feeWithCouponPercent = parsePercent(
        data.buyer_fee_percent_with_coupon,
        Math.max(serviceFeePercent - discountPercent, 0),
      );
      cache = Object.freeze({
        serviceFeePercent,
        feeWithCouponPercent,
        discountPercent,
        affiliatePercent,
        platformNetPercent,
      });
      notify(cache);
      return cache;
    })
    .catch((err) => {
      if (!cache) {
        cache = FALLBACK;
        notify(cache);
      }
      throw err;
    })
    .finally(() => {
      inflight = null;
    });

  return inflight;
}
