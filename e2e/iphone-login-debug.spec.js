// @ts-check
/**
 * Strict iPhone-style QA: strips API Set-Cookie (Safari third-party cookie behavior),
 * registers a user, logs out storage, then logs in with the same credentials.
 * On HTTP 500, captures `Server Crash: …` from JSON + toast/error box and prints to CI/terminal.
 */
import { test, expect, devices } from '@playwright/test';

const IPHONE_14 = devices['iPhone 14'];

function trimSlash(s) {
  return String(s || '').replace(/\/+$/, '');
}

function apiOriginPattern() {
  let raw = trimSlash(process.env.E2E_API_URL || 'https://safeticket-api.onrender.com');
  raw = raw.replace(/\/?api\/?$/i, '');
  if (!/^https?:\/\//i.test(raw)) {
    raw = `https://${raw}`;
  }
  const u = new URL(raw);
  return `${u.origin}/api/**`;
}

test.use({
  browserName: 'chromium',
  viewport: IPHONE_14.viewport,
  userAgent: IPHONE_14.userAgent,
  deviceScaleFactor: IPHONE_14.deviceScaleFactor,
  isMobile: IPHONE_14.isMobile,
  hasTouch: IPHONE_14.hasTouch,
  locale: 'he-IL',
});

async function stripApiSetCookieRoute(page, pat) {
  await page.route(pat, async (route) => {
    try {
      const res = await route.fetch();
      const body = await res.body();
      const headers = Object.fromEntries(
        Object.entries(res.headers()).filter(([k]) => k.toLowerCase() !== 'set-cookie')
      );
      await route.fulfill({ status: res.status(), headers, body });
    } catch {
      try {
        await route.abort('failed');
      } catch {
        /* page navigated / context closed */
      }
    }
  });
}

test.beforeEach(async ({ page }) => {
  await stripApiSetCookieRoute(page, apiOriginPattern());
});

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test.describe('iPhone Safari login debug', () => {
  test('register then login succeeds (Bearer-only; 500 surfaces Server Crash in UI)', async ({
    page,
  }) => {
    test.setTimeout(300_000);
    const DEFAULT_API = 'https://safeticket-api.onrender.com';
    const DEFAULT_WEB = 'https://safeticket-web.onrender.com';
    const envBase = process.env.E2E_BASE_URL;
    const apiBase = trimSlash(process.env.E2E_API_URL || envBase || DEFAULT_API);
    let webBase = trimSlash(process.env.E2E_WEB_URL || envBase || DEFAULT_WEB);
    if (webBase === apiBase && apiBase === trimSlash(DEFAULT_API)) {
      webBase = trimSlash(DEFAULT_WEB);
    }

    const ts = Date.now();
    const password = process.env.E2E_LOGIN_PASSWORD || 'IphoneLoginQA2026!';
    const email = process.env.E2E_LOGIN_EMAIL || `iphone_login_${ts}@e2e.local`;

    await page.goto(`${webBase}/register`, { waitUntil: 'domcontentloaded', timeout: 180_000 });
    await expect(page.locator('#email')).toBeVisible({ timeout: 90_000 });
    await page.locator('#first_name').fill('iPhone');
    await page.locator('#last_name').fill(`QA${ts}`);
    await page.locator('#email').fill(email);
    await page.locator('#password').fill(password);
    await page.locator('#password2').fill(password);

    const regPost = page.waitForResponse(
      (r) => r.url().includes('/users/register') && r.request().method() === 'POST',
      { timeout: 120_000 }
    );
    await page.getByRole('button', { name: 'הרשמה' }).click();
    const regRes = await regPost;
    if (!regRes.ok()) {
      const t = await regRes.text();
      console.error('[REGISTER_FAILED]', regRes.status(), t.slice(0, 1200));
    }
    expect(regRes.ok(), `register must succeed, got ${regRes.status()}`).toBeTruthy();

    await page.waitForURL((u) => !String(u.pathname).endsWith('/register'), { timeout: 120_000 });
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);

    await page.evaluate(() => {
      try {
        localStorage.removeItem('safeticket_jwt_access');
        localStorage.removeItem('safeticket_jwt_refresh');
      } catch {
        /* ignore */
      }
    });

    await page.goto(`${webBase}/login`, { waitUntil: 'domcontentloaded', timeout: 120_000 });
    await expect(page.locator('#username')).toBeVisible({ timeout: 60_000 });

    const loginPost = page.waitForResponse(
      (r) => r.url().includes('/users/login') && r.request().method() === 'POST',
      { timeout: 120_000 }
    );

    await page.locator('#username').fill(email);
    await page.locator('#password').fill(password);
    await page.getByRole('button', { name: 'התחברות' }).click();

    const loginRes = await loginPost;
    const loginText = await loginRes.text();
    let loginJson = {};
    try {
      loginJson = JSON.parse(loginText);
    } catch {
      loginJson = {};
    }

    if (loginRes.status() >= 500) {
      const detail =
        (typeof loginJson.detail === 'string' && loginJson.detail) ||
        loginText.slice(0, 2000);
      console.error('[LOGIN_5XX_BODY]', detail);

      const crashToast = page.getByText(/Server Crash:/i);
      const errBox = page.locator('.error-box');
      try {
        await expect(crashToast.or(errBox)).toBeVisible({ timeout: 20_000 });
      } catch {
        /* still throw with body */
      }
      const uiMsg =
        (await crashToast.first().textContent().catch(() => null)) ||
        (await errBox.first().textContent().catch(() => null)) ||
        detail;
      console.error('[UI_SERVER_CRASH_CAPTURE]', uiMsg);
      throw new Error(`Login HTTP ${loginRes.status()}: ${uiMsg}`);
    }

    expect(loginRes.ok(), `login must succeed, got ${loginRes.status()} ${loginText.slice(0, 400)}`).toBeTruthy();
    expect(loginJson.access, 'response JSON must include access for Bearer clients').toBeTruthy();

    await page.waitForURL((u) => !String(u.pathname).endsWith('/login'), { timeout: 120_000 });
    const stored = await page.evaluate(() => localStorage.getItem('safeticket_jwt_access'));
    expect(stored && stored.length > 20, 'access token must persist in localStorage').toBeTruthy();
  });
});
