/**
 * Google Ads conversion helpers. Global gtag is loaded from index.html (AW-18350905085).
 * Never throws — ads tracking must not break listing or checkout UI.
 */

export const GOOGLE_ADS_SELLER_LISTING_SEND_TO = 'AW-18350905085/QVV8COaZ0tYcEP2tsq5E';

/**
 * Fire a Google Ads conversion hit.
 * @param {string} [sendTo]
 * @returns {boolean} whether gtag was invoked
 */
export function trackGoogleAdsConversion(sendTo = GOOGLE_ADS_SELLER_LISTING_SEND_TO) {
  try {
    if (typeof window === 'undefined' || typeof window.gtag !== 'function') return false;
    window.gtag('event', 'conversion', {
      send_to: sendTo,
    });
    return true;
  } catch {
    return false;
  }
}
