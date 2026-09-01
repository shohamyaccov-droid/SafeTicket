/** PayMe hosted checkout: new tab + waiting-room helpers. */

export const PAYME_WAIT_POLL_MS = 3000;

export function shouldUsePaymeCheckout() {
  return import.meta.env.PROD ? true : import.meta.env.VITE_USE_PAYME === 'true';
}

export function openBlankPaymeTab() {
  if (typeof window === 'undefined' || typeof window.open !== 'function') return null;
  try {
    return window.open('about:blank', '_blank');
  } catch {
    return null;
  }
}

export function openPaymeCheckoutTab(url) {
  if (!url || typeof window === 'undefined' || typeof window.open !== 'function') return null;
  try {
    return window.open(url, '_blank');
  } catch {
    return null;
  }
}

export function navigatePaymeTab(tab, url) {
  if (!tab || tab.closed || !url) return false;
  try {
    tab.location.replace(url);
    return true;
  } catch {
    try {
      tab.location.href = url;
      return true;
    } catch {
      return false;
    }
  }
}

export function closePaymeTab(tab) {
  if (!tab || tab.closed) return;
  try {
    tab.close();
  } catch {
    /* popup may already be gone */
  }
}

export function isPaidOrderStatus(status) {
  return status === 'paid' || status === 'completed';
}

export function isCancelledOrderStatus(status) {
  return status === 'cancelled' || status === 'canceled';
}
