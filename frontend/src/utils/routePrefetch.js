/**
 * Warm heavy lazy route chunks after first paint so paid / sell / event
 * navigations skip the Suspense skeleton on mobile in-app browsers.
 */

let eventDetailsPrefetch = null;
let sellPrefetch = null;

export function prefetchEventDetailsPage() {
  if (!eventDetailsPrefetch) {
    eventDetailsPrefetch = import('../pages/EventDetailsPage');
  }
  return eventDetailsPrefetch;
}

export function prefetchSellPage() {
  if (!sellPrefetch) {
    sellPrefetch = import('../pages/Sell');
  }
  return sellPrefetch;
}

export function prefetchCriticalRoutesOnIdle() {
  if (typeof window === 'undefined') return () => {};

  const run = () => {
    prefetchEventDetailsPage();
    prefetchSellPage();
  };

  if (typeof window.requestIdleCallback === 'function') {
    const id = window.requestIdleCallback(run, { timeout: 2500 });
    return () => window.cancelIdleCallback(id);
  }

  const timer = window.setTimeout(run, 900);
  return () => window.clearTimeout(timer);
}
