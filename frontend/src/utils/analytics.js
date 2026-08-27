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

/** In-memory double-click lock (ticket id → last fire ms). */
const beginCheckoutClickLock = new Map();
const BEGIN_CHECKOUT_CLICK_MS = 2000;
/** Collapse Buy Now + Continue-to-payment for the same listing into one ads event. */
const BEGIN_CHECKOUT_TTL_MS = 10 * 60 * 1000;

/**
 * True when the listing-create HTTP response is success.
 * Missing status (unit-test mocks) is treated as success only if `data` is present.
 */
export function isListingCreateHttpSuccess(response) {
  const status = response?.status;
  if (status == null) return Boolean(response?.data);
  const n = Number(status);
  return Number.isFinite(n) && n >= 200 && n < 300;
}

/** First created ticket id from POST /tickets/ (single object or `{ tickets: [] }`). */
export function listingIdFromCreateResponse(data) {
  if (!data) return null;
  if (Array.isArray(data)) {
    const hit = data.find((row) => row?.id != null);
    return hit?.id ?? null;
  }
  if (Array.isArray(data.tickets)) {
    const hit = data.tickets.find((row) => row?.id != null);
    return hit?.id ?? null;
  }
  return data.id ?? null;
}

function shouldFireBeginCheckout(ticketId) {
  const key = String(ticketId ?? '');
  if (!key) return false;
  const now = Date.now();
  const lastClick = beginCheckoutClickLock.get(key) || 0;
  if (now - lastClick < BEGIN_CHECKOUT_CLICK_MS) return false;
  beginCheckoutClickLock.set(key, now);
  try {
    const storageKey = `_tt_an_begin_checkout_${key}`;
    const prev = Number(sessionStorage.getItem(storageKey) || '');
    if (Number.isFinite(prev) && prev > 0 && now - prev < BEGIN_CHECKOUT_TTL_MS) {
      return false;
    }
    sessionStorage.setItem(storageKey, String(now));
  } catch {
    /* private mode: click lock still applies */
  }
  return true;
}

/** Test helper — clear conversion guards between specs. */
export function _resetAnalyticsConversionGuardsForTests() {
  beginCheckoutClickLock.clear();
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

  /** Buyer tapped קנה עכשיו on a listing (before checkout modal). */
  addToCart: (ticketId, extra = {}) => {
    trackEvent('add_to_cart', window.location.pathname, {
      ticket_id: ticketId,
      ...extra,
    });
    const qty = extra.quantity != null ? Number(extra.quantity) : 1;
    trackGa4Event('add_to_cart', {
      currency: extra.currency || 'ILS',
      value: extra.value,
      items:
        ticketId != null
          ? [{ item_id: String(ticketId), quantity: Number.isFinite(qty) && qty > 0 ? qty : 1 }]
          : undefined,
    });
  },

  /**
   * Meta InitiateCheckout + GA4 begin_checkout.
   * Call only from explicit קנה עכשיו / המשך לתשלום clicks — never from modal mount or PayMe redirect.
   */
  checkoutStart: (ticketId, extra = {}) => {
    if (ticketId == null || ticketId === '') return;
    if (!shouldFireBeginCheckout(ticketId)) return;
    trackEvent('checkout_start', window.location.pathname, {
      ticket_id: ticketId,
      ...extra,
    });
    const qty = extra.quantity != null ? Number(extra.quantity) : 1;
    const safeQty = Number.isFinite(qty) && qty > 0 ? qty : 1;
    trackMetaInitiateCheckout({
      ticketId,
      value: extra.value,
      currency: extra.currency || 'ILS',
      numItems: safeQty,
    });
    trackGa4Event('begin_checkout', {
      currency: extra.currency || 'ILS',
      value: extra.value,
      items: [{ item_id: String(ticketId), quantity: safeQty }],
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
   * Seller successfully listed ticket(s) — the only Meta Lead / GA4 generate_lead source.
   * Requires a listing id (created ticket) so mount/retry cannot emit a nameless Lead.
   */
  ticketListed: (extra = {}) => {
    const listingId = extra.ticketId ?? extra.listingId;
    const eventID = extra.eventID || (listingId != null ? `listing_${listingId}` : '');
    if (!eventID) return;
    if (!oncePerSession(`lead_${eventID}`)) return;
    trackEvent('ticket_listed', window.location.pathname, extra || {});
    const bonus = extra.bonusValue != null ? Number(extra.bonusValue) : 20;
    trackMetaLead({
      contentName: extra.contentName || 'ticket_listing',
      value: Number.isFinite(bonus) ? bonus : 20,
      currency: 'ILS',
      eventID,
    });
    trackGa4Event('generate_lead', {
      currency: 'ILS',
      value: Number.isFinite(bonus) ? bonus : 20,
      lead_type: 'ticket_listing',
    });
  },

  /** Offer bid — backend funnel only. Must not emit Meta Lead or GA4 generate_lead. */
  offerSubmitted: (ticketId) => {
    trackEvent('offer_submitted', window.location.pathname, { ticket_id: ticketId });
  },
};
