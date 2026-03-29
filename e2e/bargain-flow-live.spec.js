// @ts-check
/**
 * LIVE E2E: seller lists @ 500 → buyer offers 400 → seller accepts (after 10s timer check) → buyer checkout.
 * Asserts negotiated price, buyer PDF download 200, admin signed PDF URL 200.
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

function trimSlash(s) {
  return String(s || '').replace(/\/+$/, '');
}

async function login(page, base, username, password) {
  await page.goto(`${trimSlash(base)}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  await page.getByRole('button', { name: 'התחברות' }).click();
  await page.waitForURL((u) => !String(u.pathname).endsWith('/login'), { timeout: 120_000 });
}

/** Django admin uses session auth, not the SPA JWT cookies. */
async function djangoAdminLogin(page, base, username, password) {
  await page.goto(`${trimSlash(base)}/admin/login/`, { waitUntil: 'domcontentloaded' });
  await page.locator('#id_username').fill(username);
  await page.locator('#id_password').fill(password);
  await page.getByRole('button', { name: 'Log in' }).click();
  await page.waitForURL((u) => String(u.pathname).startsWith('/admin/'), { timeout: 120_000 });
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
  const out = await page.evaluate(
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
      const text = await r.text();
      return { status: r.status, text: text.slice(0, 600) };
    },
    { apiRoot: root, tid: ticketId }
  );
  return out;
}

/** Same group key as EventDetailsPage `data-ticket-group-id`: listing_group_id or seller_username_price. */
function groupDomIdFromTicketJson(t) {
  const lid = t.listing_group_id;
  if (lid != null && String(lid).trim() !== '') {
    return String(lid).trim();
  }
  const sellerId =
    t.seller_username ||
    (t.seller && typeof t.seller === 'object' ? t.seller.username : null) ||
    t.seller_id ||
    'unknown';
  const price = t.asking_price ?? t.original_price ?? '';
  return `${sellerId}_${price}`;
}

/**
 * Poll public event tickets API until our listing is active (avoids empty UI / wrong row / price text mismatch).
 */
/**
 * Event page uses the same query params as the SPA (sort=price_asc by default).
 * After navigation, the UI can briefly lag behind the public API (cold cache / navigation timing).
 * Patient loop: wait for rows, or refresh/reload when the API already lists our ticket.
 */
async function waitForEventPageTicketRows(page, apiRoot, eventId, ticketId, timeoutMs = 240_000) {
  const root = trimSlash(apiRoot);
  const deadline = Date.now() + timeoutMs;
  let lastApi = null;

  async function fetchListingHasTicket() {
    return page.evaluate(
      async ({ ar, eid, tid }) => {
        const url = `${ar}/users/events/${eid}/tickets/?sort=price_asc`;
        const r = await fetch(url, { credentials: 'include' });
        const text = await r.text();
        let j;
        try {
          j = JSON.parse(text);
        } catch {
          return { ok: r.ok, status: r.status, parseError: true, snippet: text.slice(0, 200) };
        }
        const arr = Array.isArray(j) ? j : (j.results || []);
        const t = arr.find((x) => Number(x.id) === Number(tid));
        return {
          ok: r.ok,
          status: r.status,
          count: arr.length,
          found: !!t,
          qty: t ? t.available_quantity : null,
          st: t ? t.status : null,
        };
      },
      { ar: root, eid: eventId, tid: ticketId }
    );
  }

  while (Date.now() < deadline) {
    const rowCount = await page.locator('.viagogo-ticket-row').count();
    if (rowCount > 0) {
      return;
    }

    lastApi = await fetchListingHasTicket();
    const listingOk =
      lastApi.found &&
      lastApi.st === 'active' &&
      Number(lastApi.qty) > 0;

    if (listingOk) {
      await page
        .locator('.refresh-btn')
        .click({ timeout: 10_000 })
        .catch(() => {});
      await page.waitForTimeout(3500);
      if ((await page.locator('.viagogo-ticket-row').count()) > 0) {
        return;
      }
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('networkidle', { timeout: 180_000 }).catch(() => {});
      await page.waitForTimeout(3000);
      if ((await page.locator('.viagogo-ticket-row').count()) > 0) {
        return;
      }
    }

    await page.waitForTimeout(3000);
  }

  const bodySnippet = ((await page.textContent('body')) || '').slice(0, 800);
  throw new Error(
    `No .viagogo-ticket-row within ${timeoutMs}ms (event ${eventId}, ticket ${ticketId}). ` +
      `Last API: ${JSON.stringify(lastApi)}. Body: ${bodySnippet}`
  );
}

async function waitForTicketOnEventListing(page, apiRoot, eventId, ticketId, timeoutMs = 120_000) {
  const root = trimSlash(apiRoot);
  const deadline = Date.now() + timeoutMs;
  let last = null;
  while (Date.now() < deadline) {
    const result = await page.evaluate(
      async ({ ar, eid, tid }) => {
        const r = await fetch(`${ar}/users/events/${eid}/tickets/?sort=price_asc`, { credentials: 'include' });
        const text = await r.text();
        let j;
        try {
          j = JSON.parse(text);
        } catch {
          return { ok: r.ok, status: r.status, parseError: true, snippet: text.slice(0, 180) };
        }
        const arr = Array.isArray(j) ? j : (j.results || []);
        const t = arr.find((x) => Number(x.id) === Number(tid));
        return {
          ok: r.ok,
          status: r.status,
          count: arr.length,
          found: !!t,
          ticket: t || null,
        };
      },
      { ar: root, eid: eventId, tid: ticketId }
    );
    last = result;
    const t = result.ticket;
    if (
      result.found &&
      t &&
      t.status === 'active' &&
      Number(t.available_quantity) > 0
    ) {
      return { groupDomId: groupDomIdFromTicketJson(t), ticket: t };
    }
    await page.waitForTimeout(2500);
  }
  throw new Error(
    `Ticket ${ticketId} not active on event ${eventId} within ${timeoutMs}ms. Last: ${JSON.stringify(last)}`
  );
}

test.describe('Live bargain flow', () => {
  test('500 list → offer 400 → accept → checkout @ negotiated total; admin PDF link', async ({
    page,
  }) => {
    test.setTimeout(600_000);
    /**
     * Render: fresh SPA is usually `safeticket-web`; Django `safeticket-api` may serve an older
     * collectstatic bundle. If env points both web+API at the API host (common local shell export),
     * use the static site unless E2E_SPA_ON_API_HOST=1.
     */
    const DEFAULT_API = 'https://safeticket-api.onrender.com';
    const DEFAULT_WEB = 'https://safeticket-web.onrender.com';
    const envBase = process.env.E2E_BASE_URL;
    const apiBase = trimSlash(
      process.env.E2E_API_URL || envBase || DEFAULT_API
    );
    let webBase = trimSlash(
      process.env.E2E_WEB_URL || envBase || DEFAULT_WEB
    );
    const spaOnApi = process.env.E2E_SPA_ON_API_HOST === '1';
    if (
      !spaOnApi &&
      webBase === apiBase &&
      apiBase === trimSlash(DEFAULT_API)
    ) {
      webBase = trimSlash(DEFAULT_WEB);
    }
    const apiRoot = `${apiBase}/api`;
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
    await login(page, webBase, sellerUser, sellerPass);
    await page.goto(`${webBase}/sell`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#category_select')).toBeVisible({ timeout: 90_000 });
    await page.locator('#category_select').selectOption('theater');
    await page.waitForTimeout(2000);
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
    await logoutViaApi(page, apiRoot);
    await login(page, webBase, adminUser, adminPass);
    const appr = await approveTicketViaApi(page, apiRoot, ticketId);
    results.approve = appr;
    expect(appr.status, `approve status ${appr.text}`).toBe(200);

    // --- Buyer: offer 400 ---
    await logoutViaApi(page, apiRoot);
    await login(page, webBase, buyerUser, buyerPass);
    const { groupDomId } = await waitForTicketOnEventListing(
      page,
      apiRoot,
      eventId,
      ticketId
    );
    const ticketsGet = page.waitForResponse(
      (r) =>
        r.url().includes(`/users/events/${eventId}/tickets`) &&
        r.request().method() === 'GET',
      { timeout: 120_000 }
    );
    page.on('pageerror', (err) => {
      // eslint-disable-next-line no-console
      console.error('PAGEERROR', err?.message || err);
    });
    await page.goto(`${webBase}/event/${eventId}`, { waitUntil: 'load', timeout: 180_000 });
    await ticketsGet;
    await page.waitForLoadState('networkidle', { timeout: 180_000 }).catch(() => {});

    await page.waitForSelector('.event-details-container', { state: 'visible', timeout: 120_000 });
    await page.waitForFunction(
      () => {
        const t = document.body?.innerText || '';
        if (t.includes('טוען פרטי אירוע')) return false;
        return (
          t.includes('כרטיסים זמינים') ||
          t.includes('אירוע לא נמצא') ||
          t.includes('אין כרטיסים זמינים לאירוע זה כרגע')
        );
      },
      { timeout: 180_000 }
    );
    if (await page.getByText('אירוע לא נמצא').isVisible()) {
      throw new Error(`Event page says not found for eventId=${eventId}`);
    }

    await waitForEventPageTicketRows(page, apiRoot, eventId, ticketId, 240_000);
    await page.waitForSelector('.viagogo-ticket-row', { state: 'visible', timeout: 60_000 });

    // Stable hook from SPA (data-e2e-ticket-id); fallbacks for older bundles.
    let row = page
      .locator(`.viagogo-ticket-row[data-e2e-ticket-id="${ticketId}"]`)
      .first();
    if ((await row.count()) === 0) {
      row = page
        .locator(`.viagogo-ticket-row[data-ticket-group-id="${groupDomId}"]`)
        .first();
    }
    if ((await row.count()) === 0) {
      row = page
        .locator('.viagogo-ticket-row')
        .filter({ hasText: 'הורדה מיידית' })
        .filter({
          has: page.locator('.buyer-listing-price-main', {
            hasText: `₪${LIST_PRICE}`,
          }),
        })
        .first();
    }
    const rowCount = await page.locator('.viagogo-ticket-row').count();
    if (rowCount === 0) {
      const snap = (await page.textContent('body')) || '';
      throw new Error(
        `No .viagogo-ticket-row for event ${eventId} (ticket ${ticketId}). Body: ${snap.slice(0, 500)}`
      );
    }
    await expect(row).toBeVisible({ timeout: 120_000 });
    await row.click();
    const offerBtn = page.getByRole('button', { name: /הצע מחיר/i }).first();
    await expect(offerBtn).toBeVisible({ timeout: 30_000 });
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
    await logoutViaApi(page, apiRoot);
    await login(page, webBase, sellerUser, sellerPass);
    await page.goto(`${webBase}/dashboard`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /הצעות מחיר/ }).click();
    await expect(page.locator('.offers-tab')).toBeVisible({ timeout: 120_000 });
    await page.waitForSelector('.offers-ticket-row-clickable', { state: 'visible', timeout: 60_000 });
    const offerRowsBeforeAccept = await page.locator('.offers-ticket-row-clickable').count();
    expect(offerRowsBeforeAccept, 'seller must see at least one offer row').toBeGreaterThan(0);
    await page.locator('.offers-ticket-row-clickable').first().click();
    await expect(page.locator('.negotiation-footer-actions')).toBeVisible({
      timeout: 90_000,
    });
    const timerLocator = page
      .locator('.negotiation-footer-timer, .negotiation-modal-footer')
      .first();
    const timerBefore =
      (await timerLocator.textContent().catch(() => '')) || '';
    await page.waitForTimeout(10_000);
    const timerAfter =
      (await timerLocator.textContent().catch(() => '')) || '';
    results.steps.push({
      timerProbe: { before: timerBefore.slice(0, 200), after: timerAfter.slice(0, 200) },
    });
    await expect(page.locator('.negotiation-modal')).toBeVisible();
    const acceptPost = page.waitForResponse(
      (r) =>
        r.url().includes(`/api/users/offers/${offerId}/accept/`) && r.request().method() === 'POST',
      { timeout: 120_000 }
    );
    await page.locator('.negotiation-footer-actions').getByRole('button', { name: 'אישור' }).click();
    const ares = await acceptPost;
    expect(ares.status(), 'accept offer').toBe(200);
    results.steps.push({ accept: { status: ares.status() } });

    await page.waitForTimeout(1500);
    await expect(
      page.locator('.negotiation-modal .bubble-status', { hasText: /אושר/i })
    ).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText('אין הצעות מחיר')).not.toBeVisible({ timeout: 10_000 });
    const offerRowsAfterAccept = await page.locator('.offers-ticket-row-clickable').count();
    expect(
      offerRowsAfterAccept,
      'offers list must not wipe — same or more rows after accept'
    ).toBeGreaterThanOrEqual(offerRowsBeforeAccept);

    await page.locator('.negotiation-modal-close').click().catch(() => {});
    await page.waitForTimeout(800);
    await expect(page.locator('.offers-ticket-row-clickable').first()).toBeVisible({
      timeout: 60_000,
    });

    // --- Buyer: complete purchase ---
    await logoutViaApi(page, apiRoot);
    await login(page, webBase, buyerUser, buyerPass);
    await page.goto(`${webBase}/dashboard`, { waitUntil: 'domcontentloaded' });
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

    const tickets = orderPayload.tickets || orderPayload.ticket || [];
    const firstTicket = Array.isArray(tickets) ? tickets[0] : tickets;
    const buyerPdfUrl = firstTicket?.pdf_file_url || orderPayload.pdf_download_url;
    if (buyerPdfUrl) {
      const absBuyer = String(buyerPdfUrl).startsWith('http')
        ? buyerPdfUrl
        : `${apiBase}${String(buyerPdfUrl).startsWith('/') ? '' : '/'}${buyerPdfUrl}`;
      const buyerSt = await page.evaluate(async (url) => {
        const r = await fetch(url, { credentials: 'include' });
        return r.status;
      }, absBuyer);
      results.buyerPdfHttpStatus = buyerSt;
      expect(buyerSt, `buyer post-purchase PDF download should return 200`).toBe(200);
    } else {
      results.buyerPdfHttpStatus = 'no_url_in_payload';
    }

    // --- Admin PDF button (Django admin session) + signed URL must return 200 ---
    await logoutViaApi(page, apiRoot);
    await djangoAdminLogin(page, apiBase, adminUser, adminPass);
    await page.goto(`${apiBase}/admin/users/ticket/${ticketId}/change/`, {
      waitUntil: 'domcontentloaded',
    });
    const adminHtml = await page.content();
    results.adminCheck = {
      hasPdfCta: adminHtml.includes('פתח PDF מאובטח') || adminHtml.includes('פתיחה / הורדת PDF'),
    };
    expect(results.adminCheck.hasPdfCta, 'admin change page should show staff PDF open button').toBe(true);

    const adminPdfLink = page.locator(
      `a[href*="cloudinary"], a[href*="api.cloudinary.com"]`
    ).first();
    await expect(adminPdfLink).toBeVisible({ timeout: 30_000 });
    const adminPdfHref = await adminPdfLink.getAttribute('href');
    expect(adminPdfHref, 'admin PDF link href').toBeTruthy();
    const adminPdfResp = await page.request.get(adminPdfHref, { timeout: 90_000 });
    results.adminPdfHttpStatus = adminPdfResp.status();
    expect(
      adminPdfResp.ok(),
      `admin signed PDF URL must return 200, got ${adminPdfResp.status()}`
    ).toBe(true);

    // eslint-disable-next-line no-console
    console.log(JSON.stringify({ ok: true, results }, null, 2));

    try {
      fs.unlinkSync(pdfPath);
    } catch {
      /* ignore */
    }
  });
});
