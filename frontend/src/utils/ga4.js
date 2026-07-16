/**
 * Google Analytics 4 (react-ga4).
 *
 * Production-only: never initialize or send hits on localhost / 127.0.0.1
 * (or other local-style hosts). Safe to call from any route — no-ops in dev.
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

/** Test helper — reset init flag between unit tests. */
export function _resetGa4ForTests() {
  initialized = false;
}
