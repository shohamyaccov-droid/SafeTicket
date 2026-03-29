// @ts-check
/**
 * Mobile (iPhone) LIVE E2E: UI register → upgrade to seller → list → admin approve →
 * buyer offer → seller accept → checkout → PDF download. Asserts fee math.
 */
import { test, expect, devices } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

/** iPhone 13 geometry + UA on Chromium (WebKit optional in CI/local). */
const IPHONE_13 = devices['iPhone 13'];
test.use({
  browserName: 'chromium',
  viewport: IPHONE_13.viewport,
  userAgent: IPHONE_13.userAgent,
  deviceScaleFactor: IPHONE_13.deviceScaleFactor,
  isMobile: IPHONE_13.isMobile,
  hasTouch: IPHONE_13.hasTouch,
  locale: 'he-IL',
});

const MINIMAL_PDF =
  '%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 3 3]/Parent 2 0 R>>endobj trailer<</Size 4/Root 1 0 R>>\n%%EOF';

const LIST_PRICE = 500;
const OFFER_BASE = 400;

function trimSlash(s) {
  return String(s || '').replace(/\/+$/, '');
}

function expectedBuyerTotalFromBase(base) {
  const b = Math.round(Number(base) * 100) / 100;
  const baseAg = Math.round(b * 100);
  const feeAg = Math.round((baseAg * 10) / 100);
  return (baseAg + feeAg) / 100;
}

async function login(page, base, username, password) {
  await page.goto(`${trimSlash(base)}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  await page.getByRole('button', { name: 'התחברות' }).click();
  await page.waitForURL((u) => !String(u.pathname).endsWith('/login'), { timeout: 120_000 });
}

async function logoutViaApi(page, apiRoot) {
  const root = trimSlash(apiRoot);
  await page.evaluate(async (ar) => {
    try {
      const csrfR = await fetch(`${ar}/users/csrf/`, { credentials: 'include' });
      const csrfD = await csrfR.json().catch(() => ({}));
      const token = csrfD.csrfToken || '';
      await fetch(`${ar}/users/logout/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-CSRFToken': token } : {}),
        },
        body: '{}',
      });
    } catch {
      /* ignore */
    }
  }, root);
}

async function approveTicketViaApi(page, apiRoot, ticketId) {
  const root = trimSlash(apiRoot);
  return page.evaluate(
    async ({ apiRoot: ar, tid }) => {
      const csrfR = await fetch(`${ar}/users/csrf/`, { credentials: 'include' });
      const csrfD = await csrfR.json().catch(() => ({}));
      const token = csrfD.csrfToken || '';
      const r = await fetch(`${ar}/users/admin/tickets/${tid}/approve/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-CSRFToken': token } : {}),
        },
        body: '{}',
      });
      return { status: r.status };
    },
    { apiRoot: root, tid: ticketId }
  );
}

test.describe('Live bargain flow (mobile iPhone)', () => {
  test('register → seller → list → offer → accept → checkout; PDF on mobile', async ({ page }) => {
    test.setTimeout(600_000);
    const DEFAULT_API = 'https://safeticket-api.onrender.com';
    const DEFAULT_WEB = 'https://safeticket-web.onrender.com';
    const envBase = process.env.E2E_BASE_URL;
    const apiBase = trimSlash(process.env.E2E_API_URL || envBase || DEFAULT_API);
    let webBase = trimSlash(process.env.E2E_WEB_URL || envBase || DEFAULT_WEB);
    if (
      process.env.E2E_SPA_ON_API_HOST !== '1' &&
      webBase === apiBase &&
      apiBase === trimSlash(DEFAULT_API)
    ) {
      webBase = trimSlash(DEFAULT_WEB);
    }
    const apiRoot = `${apiBase}/api`;
    const adminUser = process.env.E2E_ADMIN_USERNAME || 'qa_bot';
    const adminPass = process.env.E2E_ADMIN_PASSWORD || 'SafeTicketQA2026!';
    const buyerUser = process.env.E2E_BUYER_USERNAME || 'israeli_demo_buyer';
    const buyerPass = process.env.E2E_BUYER_PASSWORD || 'DemoBuyer123!';

    const ts = Date.now();
    const regEmail = `e2e_mob_${ts}@e2e.local`;
    const newPass = 'E2EMobile2026!a';
    const expectTotal = expectedBuyerTotalFromBase(OFFER_BASE);

    const pdfPath = path.join(os.tmpdir(), `safeticket-mobile-${ts}.pdf`);
    fs.writeFileSync(pdfPath, MINIMAL_PDF, 'utf8');

    // --- Register (SPA UI, mobile) ---
    await page.goto(`${webBase}/register`, { waitUntil: 'domcontentloaded', timeout: 180_000 });
    await expect(page.locator('#email')).toBeVisible({ timeout: 90_000 });
    await page.locator('#first_name').fill('Mobile');
    await page.locator('#last_name').fill(`E2E${ts}`);
    await page.locator('#email').fill(regEmail);
    await page.locator('#password').fill(newPass);
    await page.locator('#password2').fill(newPass);
    await page.getByRole('button', { name: 'הרשמה' }).click();
    await page.waitForURL((u) => !String(u.pathname).endsWith('/register'), { timeout: 180_000 });

    // --- Upgrade + list ---
    await page.goto(`${webBase}/sell`, { waitUntil: 'load', timeout: 180_000 });
    await expect(page.locator('[data-e2e="sell-upgrade-cta"]')).toBeVisible({ timeout: 120_000 });
    await page.locator('[data-e2e="sell-upgrade-cta"]').click();
    await expect(page.locator('[data-e2e="become-seller-modal"]')).toBeVisible({ timeout: 30_000 });
    await page.locator('.become-seller-modal input[type="tel"]').fill('050-1234567');
    await page.locator('.become-seller-modal textarea').fill('paypal: seller-e2e-mobile@example.com');
    await page.locator('[data-e2e="escrow-terms-checkbox"]').check();
    const upgradeResp = page.waitForResponse(
      (r) => r.url().includes('/users/me/upgrade-to-seller/') && r.request().method() === 'POST',
      { timeout: 120_000 }
    );
    await page.locator('[data-e2e="become-seller-submit"]').click();
    const up = await upgradeResp;
    expect(up.ok()).toBeTruthy();

    await expect(page.locator('#category_select')).toBeVisible({ timeout: 120_000 });
    await page.locator('#category_select').selectOption('theater');
    await page.waitForTimeout(1500);
    await page.locator('#event_select').selectOption({ index: 1 });
    await page.locator('#original_price').fill(String(LIST_PRICE));
    await page.locator('#single_multi_page_pdf').setInputFiles(pdfPath);
    await page.locator('#acceptedTerms').check();

    const createTicketResp = page.waitForResponse(
      (r) =>
        r.url().includes('/api/users/tickets/') &&
        r.request().method() === 'POST' &&
        !r.url().includes('download'),
      { timeout: 180_000 }
    );
    await page.getByRole('button', { name: /הצע כרטיס למכירה/ }).click();
    const tres = await createTicketResp;
    expect(tres.status()).toBe(201);
    const tjson = await tres.json();
    const ticketId = tjson.id;
    const eventId = tjson.event?.id ?? tjson.event_id;

    await logoutViaApi(page, apiRoot);
    await login(page, webBase, adminUser, adminPass);
    const appr = await approveTicketViaApi(page, apiRoot, ticketId);
    expect(appr.status).toBe(200);

    await logoutViaApi(page, apiRoot);
    await login(page, webBase, buyerUser, buyerPass);
    await page.goto(`${webBase}/event/${eventId}`, { waitUntil: 'load', timeout: 180_000 });
    await page.waitForSelector('.viagogo-ticket-row', { state: 'visible', timeout: 120_000 });
    const ourRow = page
      .locator(`.viagogo-ticket-row[data-e2e-ticket-id="${ticketId}"]`)
      .or(page.locator('.viagogo-ticket-row').filter({ hasText: `₪${LIST_PRICE}` }))
      .first();
    await expect(ourRow).toBeVisible({ timeout: 90_000 });
    await ourRow.click();
    await page.getByRole('button', { name: /הצע מחיר/i }).first().click();
    await page.locator('#offerAmount').fill(String(OFFER_BASE));

    let offerId;
    for (let attempt = 0; attempt < 8; attempt++) {
      if (attempt > 0) await page.waitForTimeout(15_000);
      const offerPost = page.waitForResponse(
        (r) => r.url().includes('/api/users/offers/') && r.request().method() === 'POST',
        { timeout: 120_000 }
      );
      await page.getByRole('button', { name: /שלח הצעה/ }).click();
      const ores = await offerPost;
      if (ores.status() === 429) continue;
      expect(ores.status()).toBe(201);
      const offerJson = await ores.json();
      offerId = offerJson.id;
      break;
    }
    expect(offerId).toBeTruthy();

    await logoutViaApi(page, apiRoot);
    await login(page, webBase, regEmail, newPass);
    await page.goto(`${webBase}/dashboard`, { waitUntil: 'load', timeout: 180_000 });
    await page.waitForLoadState('networkidle', { timeout: 180_000 }).catch(() => {});
    await page.getByRole('button', { name: /הצעות מחיר/ }).click();
    await expect(page.locator('.offers-tab')).toBeVisible({ timeout: 120_000 });
    await page.waitForTimeout(4000);
    await page.getByRole('button', { name: /רענן/ }).click().catch(() => {});
    await page.waitForTimeout(2000);
    await page.waitForSelector('.offers-ticket-row-clickable', { state: 'visible', timeout: 180_000 });
    await page.locator('.offers-ticket-row-clickable').first().click();
    await expect(page.locator('.negotiation-footer-actions')).toBeVisible({ timeout: 90_000 });
    await page.waitForTimeout(10_000);
    const acceptPost = page.waitForResponse(
      (r) =>
        r.url().includes(`/api/users/offers/${offerId}/accept/`) && r.request().method() === 'POST',
      { timeout: 120_000 }
    );
    await page.locator('.negotiation-footer-actions').getByRole('button', { name: 'אישור' }).click();
    expect((await acceptPost).ok()).toBeTruthy();

    await logoutViaApi(page, apiRoot);
    await login(page, webBase, buyerUser, buyerPass);
    await page.goto(`${webBase}/dashboard`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /הצעות מחיר/ }).click();
    await page.waitForTimeout(1200);
    const completePurchaseBtn = page
      .locator('.offers-ticket-row-clickable')
      .filter({ has: page.locator('button.checkout-btn') })
      .locator('button.checkout-btn')
      .filter({ hasText: 'השלם רכישה' })
      .first();
    await expect(completePurchaseBtn).toBeVisible({ timeout: 60_000 });
    await completePurchaseBtn.click();
    await expect(page.getByRole('heading', { name: /תשלום מאובטח/ })).toBeVisible({ timeout: 60_000 });
    const expectTotalStr = expectTotal.toFixed(2);
    await expect(page.locator('.modal-content .price-breakdown .total-row').last()).toContainText(
      expectTotalStr
    );
    await page.getByRole('button', { name: 'המשך לתשלום' }).click();
    await expect(page.locator('.modal-content .price-breakdown .total-row').last()).toContainText(
      expectTotalStr
    );
    await page.locator('#cardholderName').scrollIntoViewIfNeeded();
    await page.locator('#cardholderName').fill('E2E Mobile');
    await page.locator('#cardNumber').fill('4111111111111111');
    await page.locator('#expiryDate').fill('12/30');
    await page.locator('#cvv').fill('123');
    const submitPay = page.getByRole('button', { name: /השלמת תשלום/ });
    const confirmPay = page.waitForResponse(
      (r) =>
        r.url().includes('/api/users/orders/') &&
        r.url().includes('/confirm-payment/') &&
        r.request().method() === 'POST',
      { timeout: 240_000 }
    );
    // Narrow mobile viewport often leaves the submit outside Playwright's clickable viewport.
    await submitPay.evaluate((el) => el.click());
    const cres = await confirmPay;
    expect(cres.ok()).toBeTruthy();
    const orderPayload = await cres.json();
    expect(Number(orderPayload.final_negotiated_price)).toBe(OFFER_BASE);
    expect(Number(orderPayload.total_amount ?? orderPayload.total_paid_by_buyer)).toBeCloseTo(
      expectTotal,
      2
    );

    await expect(page.getByRole('heading', { name: /Order Confirmed/i })).toBeVisible({ timeout: 60_000 });
    const pdfBtn = page.locator('[data-e2e="checkout-success-pdf"]').first();
    await expect(pdfBtn).toBeVisible({ timeout: 30_000 });
    const downloadPromise = page.waitForEvent('download', { timeout: 120_000 });
    await pdfBtn.click();
    const dl = await downloadPromise;
    expect(dl.suggestedFilename().toLowerCase()).toMatch(/\.pdf$/);

    try {
      fs.unlinkSync(pdfPath);
    } catch {
      /* ignore */
    }
  });
});
