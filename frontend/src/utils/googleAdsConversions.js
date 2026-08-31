/**
 * Google Ads conversion helpers. Global gtag is loaded from index.html (AW-18350905085).
 * Never throws — ads tracking must not break listing or checkout UI.
 */

export const GOOGLE_ADS_AW_ID = 'AW-18350905085';
export const GOOGLE_ADS_SELLER_LISTING_SEND_TO = `${GOOGLE_ADS_AW_ID}/QVV8COaZ0tYcEP2tsq5E`;

let ensuredGtag = false;

/**
 * Ensure the Google Ads gtag snippet is present (index.html, or inject if a
 * cached/stripped SPA shell omitted it). Safe to call on every route change.
 * @returns {boolean}
 */
export function ensureGoogleAdsTag() {
  try {
    if (typeof window === 'undefined' || typeof document === 'undefined') return false;
    if (ensuredGtag && typeof window.gtag === 'function') return true;
    if (typeof window.gtag === 'function') {
      ensuredGtag = true;
      return true;
    }

    window.dataLayer = window.dataLayer || [];
    window.gtag = function gtag() {
      window.dataLayer.push(arguments);
    };

    const src = `https://www.googletagmanager.com/gtag/js?id=${GOOGLE_ADS_AW_ID}`;
    const already = document.querySelector(`script[src="${src}"]`);
    if (!already) {
      const script = document.createElement('script');
      script.async = true;
      script.src = src;
      document.head.appendChild(script);
    }

    window.gtag('js', new Date());
    window.gtag('config', GOOGLE_ADS_AW_ID);
    ensuredGtag = true;
    return true;
  } catch {
    return false;
  }
}

/** Test helper */
export function _resetGoogleAdsTagForTests() {
  ensuredGtag = false;
}

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
