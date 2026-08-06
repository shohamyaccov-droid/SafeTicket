/**
 * Safari / cross-origin checkout auth — session persistence tests.
 *
 * Scenarios: Desktop cookie auth, iOS Safari Bearer-only, Android Chrome,
 * logged-in-before-checkout, guest checkout, concurrent refresh, 403≠logout.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { isCheckoutAuthSessionFailure } from '../utils/checkoutAuth';

describe('isCheckoutAuthSessionFailure', () => {
  it('treats 401 as session failure (expired JWT)', () => {
    expect(isCheckoutAuthSessionFailure({ response: { status: 401 } })).toBe(true);
  });

  it('does not treat PayMe Forbidden 403 as session failure (Safari cookie-less bug)', () => {
    expect(
      isCheckoutAuthSessionFailure({ response: { status: 403, data: { error: 'Forbidden.' } } }),
    ).toBe(false);
  });

  it('does not treat CSRF 403 as session failure', () => {
    expect(
      isCheckoutAuthSessionFailure({
        response: { status: 403, data: 'CSRF verification failed' },
      }),
    ).toBe(false);
  });

  it('ignores network errors without status', () => {
    expect(isCheckoutAuthSessionFailure(new Error('network'))).toBe(false);
  });
});

describe('Authorization strip policy (Safari vs guest)', () => {
  it('keeps Bearer on payme/init for logged-in buyers', async () => {
    const { shouldStripAuthorization } = await import('./api.js');
    expect(shouldStripAuthorization('/users/payments/payme/init/', false)).toBe(false);
  });

  it('strips Bearer on payme/init only when guest skipAuth is set', async () => {
    const { shouldStripAuthorization } = await import('./api.js');
    expect(shouldStripAuthorization('/users/payments/payme/init/', true)).toBe(true);
  });

  it('keeps Bearer on reserve for logged-in buyers', async () => {
    const { shouldStripAuthorization } = await import('./api.js');
    expect(shouldStripAuthorization('/users/tickets/42/reserve/', false)).toBe(false);
  });

  it('strips Bearer on guest order endpoint', async () => {
    const { shouldStripAuthorization } = await import('./api.js');
    expect(shouldStripAuthorization('/users/orders/guest/', false)).toBe(true);
  });
});

describe('notifySessionExpired debounce', () => {
  beforeEach(async () => {
    vi.resetModules();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('emits a single session-expired event under burst notify calls', async () => {
    const apiMod = await import('./api.js');
    apiMod.__resetAuthSessionStateForTests();
    let count = 0;
    const handler = () => {
      count += 1;
    };
    window.addEventListener(apiMod.SESSION_EXPIRED_EVENT, handler);
    apiMod.notifySessionExpired();
    apiMod.notifySessionExpired();
    apiMod.notifySessionExpired();
    window.removeEventListener(apiMod.SESSION_EXPIRED_EVENT, handler);
    expect(count).toBe(1);
  });
});

describe('refreshAccessToken single-flight (mobile concurrent 401s)', () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shares one refresh POST across concurrent callers', async () => {
    const apiMod = await import('./api.js');
    apiMod.__resetAuthSessionStateForTests();
    apiMod.setBearerFallback('old-access', 'refresh-token-1');

    const postSpy = vi.spyOn(apiMod.default, 'post').mockImplementation(async (url) => {
      if (String(url).includes('token/refresh')) {
        await new Promise((r) => setTimeout(r, 40));
        return { data: { access: 'access-B', refresh: 'refresh-B' } };
      }
      return { data: {} };
    });

    const [a, b, c] = await Promise.all([
      apiMod.refreshAccessToken(),
      apiMod.refreshAccessToken(),
      apiMod.refreshAccessToken(),
    ]);

    expect(a).toBe('access-B');
    expect(b).toBe('access-B');
    expect(c).toBe('access-B');
    const refreshPosts = postSpy.mock.calls.filter(([url]) => String(url).includes('token/refresh'));
    expect(refreshPosts.length).toBe(1);
    expect(apiMod.getEffectiveBearerAccess()).toBe('access-B');
  });
});
