/**
 * Lightweight analytics tracker.
 *
 * Sends a single fire-and-forget POST to the backend for each user action.
 * Never blocks the UI — all network errors are silently swallowed.
 *
 * Session ID:
 *   A random UUID is generated once per browser session (sessionStorage) so
 *   the backend can count unique visitors without tracking users across sessions
 *   or storing any PII.
 */

const ANALYTICS_ENDPOINT = '/api/users/analytics/track/';

/** Lazily creates and caches the anonymous session ID for this browser session. */
function getSessionId() {
  const KEY = '_tt_sid';
  let id = sessionStorage.getItem(KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(KEY, id);
  }
  return id;
}

/**
 * Track an analytics event.
 *
 * @param {'page_view'|'checkout_start'|'checkout_complete'|'offer_submitted'|'ticket_viewed'} eventType
 * @param {string} [path]  URL path to record; defaults to window.location.pathname
 * @param {object} [data]  Optional extra context (e.g. { event_id: 12 })
 */
export function trackEvent(eventType, path, data = {}) {
  try {
    const payload = {
      session_id: getSessionId(),
      path: path || window.location.pathname,
      event_type: eventType,
      event_data: data || {},
    };

    // Use sendBeacon when available (survives page unloads); fall back to fetch.
    const body = JSON.stringify(payload);
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: 'application/json' });
      navigator.sendBeacon(ANALYTICS_ENDPOINT, blob);
    } else {
      fetch(ANALYTICS_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
      }).catch(() => {});
    }
  } catch {
    // Never throw — analytics must never break the main app.
  }
}

/**
 * Convenience wrappers for the main funnel steps.
 */
export const Analytics = {
  pageView: (path) => trackEvent('page_view', path),
  ticketViewed: (eventId) =>
    trackEvent('ticket_viewed', `/events/${eventId}`, { event_id: eventId }),
  checkoutStart: (ticketId) =>
    trackEvent('checkout_start', window.location.pathname, { ticket_id: ticketId }),
  checkoutComplete: (orderId) =>
    trackEvent('checkout_complete', window.location.pathname, { order_id: orderId }),
  offerSubmitted: (ticketId) =>
    trackEvent('offer_submitted', window.location.pathname, { ticket_id: ticketId }),
};
