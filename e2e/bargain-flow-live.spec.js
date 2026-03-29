// @ts-check
/**
 * LIVE E2E: seller lists @ 500 → buyer offers 400 → seller accepts → buyer checkout.
 * Asserts negotiated base 400, total charged ceil(400*1.1)=440, admin PDF button present.
 */
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const MINIMAL_PDF =
  '%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 3 3]/Parent 2 0 R>>endobj trailer<</Size 4/Root 1 0 R>>\n%%EOF';

const LIST_PRICE = 500;
const OFFER_BASE = 400;
const EXPECT_TOTAL = Math.ceil(OFFER_BASE * 1.1);

async function login(page, base, username, password) {
  await page.goto(`${base}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  await page.getByRole('button', { name: 'התחברות' }).click();
  await page.waitForURL((u) => !String(u.pathname).endsWith('/login'), { timeout: 120_000 });
}

/** Django admin uses session auth, not the SPA JWT cookies. */
async function djangoAdminLogin(page, base, username, password) {
  await page.goto(`${base}/admin/login/`, { waitUntil: 'domcontentloaded' });
  await page.locator('#id_username').fill(username);
  await page.locator('#id_password').fill(password);
  await page.getByRole('button', { name: 'Log in' }).click();
  await page.waitForURL((u) => String(u.pathname).startsWith('/admin/'), { timeout: 120_000 });
}

async function approveTicketViaApi(page, ticketId) {
  const out = await page.evaluate(async (tid) => {
    const origin = window.location.origin;
    const csrfR = await fetch(`${origin}/api/users/csrf/`, { credentials: 'include' });
    const csrfD = await csrfR.json().catch(() => ({}));
    const token = csrfD.csrfToken || '';
    const r = await fetch(`${origin}/api/users/admin/tickets/${tid}/approve/`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'X-CSRFToken': token } : {}),
      },
      body: '{}',
    });
    const text = await r.text();
    return { status: r.status, text: text.slice(0, 600) };
  }, ticketId);
  return out;
}

test.describe('Live bargain flow', () => {
  test('500 list → offer 400 → accept → checkout @ negotiated total; admin PDF link', async ({
    page,
  }) => {
    const base = process.env.E2E_BASE_URL || 'https://safeticket-api.onrender.com';
    const sellerUser = process.env.E2E_SELLER_USERNAME || 'israeli_demo_seller';
    const sellerPass = process.env.E2E_SELLER_PASSWORD || 'DemoSeller123!';
    const buyerUser = process.env.E2E_BUYER_USERNAME || 'israeli_demo_buyer';
    const buyerPass = process.env.E2E_BUYER_PASSWORD || 'DemoBuyer123!';
    const adminUser = process.env.E2E_ADMIN_USERNAME || 'qa_bot';
    const adminPass = process.env.E2E_ADMIN_PASSWORD || 'SafeTicketQA2026!';

    const pdfPath = path.join(os.tmpdir(), `safeticket-bargain-${Date.now()}.pdf`);
    fs.writeFileSync(pdfPath, MINIMAL_PDF, 'utf8');

    const results = { steps: [], order: null, approve: null, adminCheck: null };

    // --- Seller: list ticket @ 500 ---
    await login(page, base, sellerUser, sellerPass);
    const createTicketResp = page.waitForResponse(
      (r) =>
        r.url().includes('/api/users/tickets/') &&
        r.request().method() === 'POST' &&
        !r.url().includes('download'),
      { timeout: 120_000 }
    );

    await page.goto(`${base}/sell`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#category_select')).toBeVisible({ timeout: 90_000 });
    await page.locator('#category_select').selectOption('theater');
    await page.waitForTimeout(2000);
    await page.locator('#event_select').selectOption({ index: 1 });
    await page.locator('#original_price').fill(String(LIST_PRICE));
    await page.locator('#single_multi_page_pdf').setInputFiles(pdfPath);
    await page.locator('#acceptedTerms').check();

    await page.getByRole('button', { name: /הצע כרטיס למכירה/ }).click();
    const tres = await createTicketResp;
    expect(tres.status(), 'ticket create 201').toBe(201);
    const tjson = await tres.json();
    const ticketId = tjson.id;
    const eventId = tjson.event?.id ?? tjson.event_id;
    expect(ticketId).toBeTruthy();
    expect(eventId).toBeTruthy();
    results.steps.push({ sell: { ticketId, eventId, status: tres.status() } });

    await expect(
      page.getByRole('heading', { name: /Listing Created Successfully/i })
    ).toBeVisible({ timeout: 60_000 });

    // --- Staff: activate listing ---
    await login(page, base, adminUser, adminPass);
    const appr = await approveTicketViaApi(page, ticketId);
    results.approve = appr;
    expect(appr.status, `approve status ${appr.text}`).toBe(200);

    // --- Buyer: offer 400 ---
    await login(page, base, buyerUser, buyerPass);
    await page.goto(`${base}/event/${eventId}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    const offerBtn = page.getByRole('button', { name: /הצע מחיר/i }).first();
    await expect(offerBtn).toBeVisible({ timeout: 90_000 });
    await offerBtn.click();
    await expect(page.locator('#offerAmount')).toBeVisible({ timeout: 30_000 });
    await page.locator('#offerAmount').fill(String(OFFER_BASE));
    const offerPost = page.waitForResponse(
      (r) => r.url().includes('/api/users/offers/') && r.request().method() === 'POST',
      { timeout: 120_000 }
    );
    await page.getByRole('button', { name: /שלח הצעה/ }).click();
    const ores = await offerPost;
    expect(ores.status(), 'create offer').toBe(201);
    const offerJson = await ores.json();
    const offerId = offerJson.id;
    expect(offerId).toBeTruthy();
    results.steps.push({ offer: { offerId, status: ores.status() } });

    // --- Seller: accept ---
    await login(page, base, sellerUser, sellerPass);
    await page.goto(`${base}/dashboard`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /הצעות מחיר/ }).click();
    await expect(page.locator('.offers-tab')).toBeVisible({ timeout: 60_000 });
    await page.locator('.offers-ticket-row-clickable').first().click();
    await expect(page.locator('.negotiation-footer-actions')).toBeVisible({
      timeout: 30_000,
    });
    const acceptPost = page.waitForResponse(
      (r) =>
        r.url().includes(`/api/users/offers/${offerId}/accept/`) && r.request().method() === 'POST',
      { timeout: 120_000 }
    );
    await page.locator('.negotiation-footer-actions').getByRole('button', { name: 'אישור' }).click();
    const ares = await acceptPost;
    expect(ares.status(), 'accept offer').toBe(200);
    results.steps.push({ accept: { status: ares.status() } });

    // --- Buyer: complete purchase ---
    await login(page, base, buyerUser, buyerPass);
    await page.goto(`${base}/dashboard`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /הצעות מחיר/ }).click();
    await page.waitForTimeout(1500);
    await page.locator('.offers-ticket-row-clickable').first().click();
    await expect(page.getByRole('button', { name: 'השלם רכישה' })).toBeVisible({ timeout: 60_000 });
    const confirmPay = page.waitForResponse(
      (r) =>
        r.url().includes('/api/users/orders/') &&
        r.url().includes('/confirm-payment/') &&
        r.request().method() === 'POST',
      { timeout: 180_000 }
    );
    await page.getByRole('button', { name: 'השלם רכישה' }).click();
    await expect(page.getByRole('heading', { name: /תשלום מאובטח/ })).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: 'המשך לתשלום' }).click();
    await page.locator('#cardholderName').fill('E2E Buyer');
    await page.locator('#cardNumber').fill('4111111111111111');
    await page.locator('#expiryDate').fill('12/30');
    await page.locator('#cvv').fill('123');
    await page.getByRole('button', { name: /השלמת תשלום/ }).click();

    const cres = await confirmPay;
    expect(cres.ok(), 'confirm payment').toBeTruthy();
    const orderPayload = await cres.json();
    results.order = {
      total_amount: orderPayload.total_amount,
      final_negotiated_price: orderPayload.final_negotiated_price,
      related_offer: orderPayload.related_offer,
    };

    const fn = Number(orderPayload.final_negotiated_price);
    const ta = Number(orderPayload.total_amount ?? orderPayload.total_paid_by_buyer);
    expect(fn, 'final_negotiated_price = offer base 400').toBe(OFFER_BASE);
    expect(ta, `total charged (buyer) = ceil(base*1.1) = ${EXPECT_TOTAL}`).toBe(EXPECT_TOTAL);

    // --- Admin PDF button (Django admin session) ---
    await djangoAdminLogin(page, base, adminUser, adminPass);
    await page.goto(`${base}/admin/users/ticket/${ticketId}/change/`, { waitUntil: 'domcontentloaded' });
    const adminHtml = await page.content();
    results.adminCheck = {
      hasPdfCta: adminHtml.includes('פתח PDF מאובטח') || adminHtml.includes('פתיחה / הורדת PDF'),
    };
    expect(results.adminCheck.hasPdfCta, 'admin change page should show staff PDF open button').toBe(true);

    // eslint-disable-next-line no-console
    console.log(JSON.stringify({ ok: true, results }, null, 2));

    try {
      fs.unlinkSync(pdfPath);
    } catch {
      /* ignore */
    }
  });
});
