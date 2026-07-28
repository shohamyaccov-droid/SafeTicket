/**
 * Google Analytics 4 (react-ga4) + dataLayer bridge for GTM.
 *
 * Production-only hits on tradetix.co.il. dataLayer pushes still run so GTM
 * can mirror events when configured. Safe to call from any route — never throws.
 */
import ReactGA from 'react-ga4';

export const GA4_MEASUREMENT_ID = 'G-D0P22V9YLH';

let initialized = false;

/**
 * @returns {boolean} Whether GA4 may send data from this browser host.
 */
export function isGa4ProductionHost(hostname = typeof window !== 'undefined' ? window.location.hostname : '') {
  const host = String(hostname || '').toLowerCase().trim();
  if (!host) return false;
  // Strict allowlist — never track on Render staging or localhost.
  return host === 'tradetix.co.il' || host === 'www.tradetix.co.il';
}

/**
 * Initialize GA4 once in production. No-op (and never throws) in local development.
 * @returns {boolean} true if GA4 is active after this call
 */
export function initGa4() {
  try {
    if (initialized) return true;
    if (typeof window === 'undefined') return false;
    if (!isGa4ProductionHost(window.location.hostname)) return false;

    ReactGA.initialize(GA4_MEASUREMENT_ID, {
      gaOptions: {
        anonymize_ip: true,
      },
    });
    initialized = true;
    return true;
  } catch {
    initialized = false;
    return false;
  }
}

/**
 * Push a GTM/dataLayer event (works even when GA4 host gate blocks).
 */
export function pushDataLayerEvent(eventName, params = {}) {
  try {
    if (typeof window === 'undefined') return;
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: eventName,
      ...params,
    });
  } catch {
    /* ignore */
  }
}

/**
 * Send a GA4 pageview for the given React Router location.
 * Initializes lazily on first production pageview.
 */
export function trackGa4Pageview(pathname, search = '') {
  try {
    if (!initGa4()) return;
    const page = `${pathname || '/'}${search || ''}`;
    ReactGA.send({ hitType: 'pageview', page, title: typeof document !== 'undefined' ? document.title : page });
  } catch {
    // Analytics must never break navigation.
  }
}

/**
 * Fire a GA4 custom / recommended event and mirror to dataLayer for GTM.
 * Examples: generate_lead, purchase, begin_checkout, view_item, add_to_cart
 *
 * @param {string} eventName
 * @param {Record<string, unknown>} [params]
 */
export function trackGa4Event(eventName, params = {}) {
  try {
    if (!eventName) return;
    const clean = { ...params };
    // Prefer numbers for monetary fields when provided as strings.
    if (clean.value != null && clean.value !== '') {
      const n = Number(clean.value);
      if (Number.isFinite(n)) clean.value = n;
    }
    pushDataLayerEvent(eventName, clean);
    if (!initGa4()) return;
    ReactGA.gtag('event', eventName, clean);
  } catch {
    /* ignore */
  }
}

/** Test helper — reset init flag between unit tests. */
export function _resetGa4ForTests() {
  initialized = false;
}
