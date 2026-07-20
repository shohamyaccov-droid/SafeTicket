/**
 * Meta (Facebook) Pixel helpers.
 * Base snippet lives in index.html; this module re-inits if the SPA boots
 * without fbq (e.g. cached HTML without the pixel) and tracks SPA PageViews.
 */
export const META_PIXEL_ID = '1267663240931005';

let ensured = false;

/** Ensure fbq exists and the pixel is initialized exactly once. */
export function ensureMetaPixel() {
  if (typeof window === 'undefined') return false;
  try {
    if (typeof window.fbq === 'function') {
      if (!ensured) {
        // Re-declare init is safe; Meta ignores duplicate init for same ID.
        window.fbq('init', META_PIXEL_ID);
        ensured = true;
      }
      return true;
    }

    // Fallback: inject base snippet if missing from document (stale deploy / stripped HTML).
    /* eslint-disable prefer-rest-params, no-unused-expressions */
    !(function (f, b, e, v, n, t, s) {
      if (f.fbq) return;
      n = f.fbq = function () {
        n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
      };
      if (!f._fbq) f._fbq = n;
      n.push = n;
      n.loaded = !0;
      n.version = '2.0';
      n.queue = [];
      t = b.createElement(e);
      t.async = !0;
      t.src = v;
      s = b.getElementsByTagName(e)[0];
      s.parentNode.insertBefore(t, s);
    })(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js');
    /* eslint-enable prefer-rest-params, no-unused-expressions */

    window.fbq('init', META_PIXEL_ID);
    window.fbq('track', 'PageView');
    ensured = true;
    return true;
  } catch {
    return false;
  }
}

export function trackMetaPageView() {
  try {
    if (!ensureMetaPixel()) return;
    window.fbq('track', 'PageView');
  } catch {
    /* analytics must never break navigation */
  }
}

export function trackMetaLead() {
  try {
    if (!ensureMetaPixel()) return;
    window.fbq('track', 'Lead');
  } catch {
    /* ignore */
  }
}
