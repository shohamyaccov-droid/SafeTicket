/**
 * Meta (Facebook) Pixel helpers.
 * Base snippet lives in index.html; this module re-inits if the SPA boots
 * without fbq (e.g. cached HTML without the pixel) and tracks SPA PageViews
 * plus conversion events (Lead / Purchase / InitiateCheckout / ViewContent).
 */
export const META_PIXEL_ID = '1267663240931005';

let ensured = false;

function safeFbq(method, eventName, params, options) {
  if (typeof window === 'undefined' || typeof window.fbq !== 'function') return false;
  if (params != null && options != null) {
    window.fbq(method, eventName, params, options);
  } else if (params != null) {
    window.fbq(method, eventName, params);
  } else {
    window.fbq(method, eventName);
  }
  return true;
}

function oncePerSession(dedupeKey) {
  if (typeof window === 'undefined' || !dedupeKey) return true;
  try {
    const key = `_tt_meta_${dedupeKey}`;
    if (sessionStorage.getItem(key)) return false;
    sessionStorage.setItem(key, '1');
    return true;
  } catch {
    return true;
  }
}

/** Ensure fbq exists and the pixel is initialized exactly once. */
export function ensureMetaPixel() {
  if (typeof window === 'undefined') return false;
  try {
    if (typeof window.fbq === 'function') {
      if (!ensured) {
        // Re-declare init is safe; Meta ignores duplicate init for same ID.
        window.fbq('init', META_PIXEL_ID);
        // Disable automatic "Lead" / "InitiateCheckout" inference from buttons and forms.
        window.fbq('set', 'autoConfig', false, META_PIXEL_ID);
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
    window.fbq('set', 'autoConfig', false, META_PIXEL_ID);
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
    safeFbq('track', 'PageView');
  } catch {
    /* analytics must never break navigation */
  }
}

/**
 * Seller listed a ticket successfully — Meta standard Lead (campaign optimization target).
 * @param {{ contentName?: string, value?: number, currency?: string, eventID?: string }} [opts]
 */
export function trackMetaLead(opts = {}) {
  try {
    if (!ensureMetaPixel()) return;
    const eventID = opts.eventID ? String(opts.eventID) : '';
    if (!eventID) return;
    if (!oncePerSession(`lead_${eventID}`)) return;
    safeFbq(
      'track',
      'Lead',
      {
        content_name: opts.contentName || 'ticket_listing',
        content_category: 'seller_listing',
        currency: opts.currency || 'ILS',
        value: typeof opts.value === 'number' ? opts.value : 20,
      },
      { eventID },
    );
  } catch {
    /* ignore */
  }
}

/**
 * Buyer completed payment (PayMe success / in-app confirm).
 * @param {{ orderId: string|number, value?: number, currency?: string }} opts
 */
export function trackMetaPurchase(opts = {}) {
  try {
    if (!ensureMetaPixel()) return;
    const orderId = opts.orderId != null ? String(opts.orderId) : '';
    if (!orderId) return;
    if (!oncePerSession(`purchase_${orderId}`)) return;
    const value = Number(opts.value);
    safeFbq(
      'track',
      'Purchase',
      {
        currency: opts.currency || 'ILS',
        value: Number.isFinite(value) ? value : 0,
        content_type: 'product',
        contents: [{ id: orderId, quantity: 1 }],
      },
      { eventID: `purchase_${orderId}` },
    );
  } catch {
    /* ignore */
  }
}

/**
 * Buyer started checkout (order created / PayMe redirect).
 */
export function trackMetaInitiateCheckout(opts = {}) {
  try {
    if (!ensureMetaPixel()) return;
    const value = Number(opts.value);
    safeFbq('track', 'InitiateCheckout', {
      currency: opts.currency || 'ILS',
      value: Number.isFinite(value) ? value : undefined,
      content_ids: opts.contentIds || (opts.ticketId != null ? [String(opts.ticketId)] : undefined),
      content_type: 'product',
      num_items: opts.numItems || 1,
    });
  } catch {
    /* ignore */
  }
}

/** Event / listing detail viewed. */
export function trackMetaViewContent(opts = {}) {
  try {
    if (!ensureMetaPixel()) return;
    safeFbq('track', 'ViewContent', {
      content_type: opts.contentType || 'product',
      content_ids: opts.contentIds,
      content_name: opts.contentName,
      currency: opts.currency || 'ILS',
      value: opts.value,
    });
  } catch {
    /* ignore */
  }
}

/** Test helper */
export function _resetMetaPixelForTests() {
  ensured = false;
}
