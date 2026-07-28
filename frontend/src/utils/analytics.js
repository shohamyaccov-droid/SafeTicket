/**
 * Lightweight analytics tracker.
 *
 * 1) Backend funnel POST (fire-and-forget)
 * 2) Meta Pixel conversion events (Lead / Purchase / …)
 * 3) GA4 + dataLayer custom events (generate_lead / purchase / …)
 *
 * Never blocks the UI — all errors are swallowed.
 */

import { API_URL } from '../services/api';
import { trackGa4Event } from './ga4';
import {
  trackMetaInitiateCheckout,
  trackMetaLead,
  trackMetaPurchase,
  trackMetaViewContent,
} from './metaPixel';

/** Absolute API URL — required when the SPA is on a separate static host from the API. */
const ANALYTICS_ENDPOINT = `${API_URL.replace(/\/+$/, '')}/users/analytics/track/`;

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

function oncePerSession(dedupeKey) {
  if (!dedupeKey) return true;
  try {
    const key = `_tt_an_${dedupeKey}`;
    if (sessionStorage.getItem(key)) return false;
    sessionStorage.setItem(key, '1');
    return true;
  } catch {
    return true;
  }
}

/**
 * Track an analytics event (backend only).
 *
 * @param {string} eventType
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
 * Convenience wrappers for the main funnel steps (backend + Meta + GA4).
 */
export const Analytics = {
  pageView: (path) => trackEvent('page_view', path),

  ticketViewed: (eventId, extra = {}) => {
    trackEvent('ticket_viewed', `/event/${eventId}`, { event_id: eventId, ...extra });
    const ids = eventId != null ? [String(eventId)] : undefined;
    trackMetaViewContent({
      contentIds: ids,
      contentName: extra.contentName || extra.name,
      value: extra.value,
    });
    trackGa4Event('view_item', {
      item_id: eventId != null ? String(eventId) : undefined,
      item_name: extra.contentName || extra.name,
      currency: 'ILS',
      value: extra.value,
    });
  },

  checkoutStart: (ticketId, extra = {}) => {
    trackEvent('checkout_start', window.location.pathname, {
      ticket_id: ticketId,
      ...extra,
    });
    trackMetaInitiateCheckout({
      ticketId,
      value: extra.value,
      currency: extra.currency || 'ILS',
      numItems: extra.quantity || 1,
    });
    trackGa4Event('begin_checkout', {
      currency: extra.currency || 'ILS',
      value: extra.value,
      items: ticketId != null ? [{ item_id: String(ticketId), quantity: extra.quantity || 1 }] : undefined,
    });
  },

  /**
   * Successful payment (in-app confirm or PayMe return).
   * Deduped per order id so polling cannot double-count.
   */
  checkoutComplete: (orderId, extra = {}) => {
    if (orderId == null) return;
    if (!oncePerSession(`purchase_${orderId}`)) return;
    trackEvent('checkout_complete', window.location.pathname, {
      order_id: orderId,
      ...extra,
    });
    const value = extra.value != null ? Number(extra.value) : undefined;
    trackMetaPurchase({
      orderId,
      value,
      currency: extra.currency || 'ILS',
    });
    trackGa4Event('purchase', {
      transaction_id: String(orderId),
      currency: extra.currency || 'ILS',
      value: Number.isFinite(value) ? value : 0,
    });
  },

  /**
   * Seller successfully listed ticket(s) — primary FB Lead + GA4 generate_lead.
   */
  ticketListed: (extra = {}) => {
    trackEvent('ticket_listed', window.location.pathname, extra || {});
    const bonus = extra.bonusValue != null ? Number(extra.bonusValue) : 20;
    trackMetaLead({
      contentName: extra.contentName || 'ticket_listing',
      value: Number.isFinite(bonus) ? bonus : 20,
      currency: 'ILS',
      eventID: extra.eventID,
    });
    trackGa4Event('generate_lead', {
      currency: 'ILS',
      value: Number.isFinite(bonus) ? bonus : 20,
      lead_type: 'ticket_listing',
    });
  },

  offerSubmitted: (ticketId) => {
    trackEvent('offer_submitted', window.location.pathname, { ticket_id: ticketId });
    trackGa4Event('generate_lead', {
      currency: 'ILS',
      lead_type: 'offer_submitted',
      item_id: ticketId != null ? String(ticketId) : undefined,
    });
  },
};
