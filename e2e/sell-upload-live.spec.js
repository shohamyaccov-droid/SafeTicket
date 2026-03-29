// @ts-check
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

/** Minimal valid-enough PDF for Magic-byte validation (%PDF) and single-page flow. */
const MINIMAL_PDF =
  '%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 3 3]/Parent 2 0 R>>endobj trailer<</Size 4/Root 1 0 R>>\n%%EOF';

test.describe('Live Sell flow', () => {
  test('login, sell form, attach PDF, submit — server accepts multipart', async ({ page }) => {
    const user = process.env.E2E_USERNAME || 'qa_bot';
    const password = process.env.E2E_PASSWORD || 'SafeTicketQA2026!';
    const base = process.env.E2E_BASE_URL || 'https://safeticket-api.onrender.com';

    const pdfPath = path.join(os.tmpdir(), `safeticket-e2e-${Date.now()}.pdf`);
    fs.writeFileSync(pdfPath, MINIMAL_PDF, 'utf8');

    const logs = [];
    page.on('console', (msg) => {
      const t = msg.text();
      if (t.includes('Frontend Version') || t.includes('FormData') || t.includes('SafeTicket')) {
        logs.push(`[browser console] ${t}`);
      }
    });

    await page.goto(`${base}/login`, { waitUntil: 'domcontentloaded' });
    await page.locator('#username').fill(user);
    await page.locator('#password').fill(password);
    await page.getByRole('button', { name: 'התחברות' }).click();

    await page.waitForURL((u) => !u.pathname.endsWith('/login'), { timeout: 60_000 });

    await page.goto(`${base}/sell`, { waitUntil: 'domcontentloaded' });

    // Sell page shows a loading shell until AuthContext resolves; build tag only appears for sellers.
    await expect(page.locator('#category_select')).toBeVisible({ timeout: 90_000 });

    // Theater: no artist gate; seeded May/Jul events stay "upcoming" longer than some concert dates.
    await page.locator('#category_select').selectOption('theater');
    await page.waitForTimeout(2500);
    const eventSelect = page.locator('#event_select');
    const optCount = await eventSelect.locator('option').count();
    if (optCount < 2) {
      console.log(JSON.stringify({ ok: false, error: 'No theater events in catalog.', optCount, logs }, null, 2));
      test.skip(true, 'No theater events on live DB');
    }
    await eventSelect.selectOption({ index: 1 });

    await page.locator('#original_price').fill('150');

    const pdfInput = page.locator('#single_multi_page_pdf');
    await pdfInput.setInputFiles(pdfPath);

    await page.locator('#acceptedTerms').check();

    const responsePromise = page.waitForResponse(
      (res) =>
        res.url().includes('/api/users/tickets/') &&
        res.request().method() === 'POST' &&
        !res.url().includes('details')
    );

    await page.getByRole('button', { name: /הצע כרטיס למכירה/ }).click();

    const res = await responsePromise;
    const status = res.status();
    let bodySnippet = '';
    try {
      const txt = await res.text();
      bodySnippet = txt.slice(0, 800);
    } catch {
      bodySnippet = '(could not read body)';
    }

    const out = {
      ok: status === 201,
      httpStatus: status,
      responsePreview: bodySnippet,
      pdfPath,
      pdfSize: fs.statSync(pdfPath).size,
      consoleHints: logs,
    };
    console.log(JSON.stringify(out, null, 2));

    expect(status, `ticket POST should succeed; body=${bodySnippet}`).toBe(201);
    await expect(page.getByRole('heading', { name: /Listing Created Successfully/i })).toBeVisible({
      timeout: 30_000,
    });

    try {
      fs.unlinkSync(pdfPath);
    } catch {
      /* ignore */
    }
  });
});
