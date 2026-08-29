# Overnight security audit — TradeTix

**Date:** 30 August 2026  
**Branch:** `main`  
**Scope:** Django REST API + React SPA. Payment/escrow, ticket uploads, IDOR, JWT/PII, phone/email enforcement.  
**Method:** Multi-pass code review, new defensive Django tests, harden, re-run until green. No exploit scripts.

This pass did **not** change PayMe production fulfillment: webhooks still finalize only after a live `get-sales` / `get-transactions` confirm. Checkout totals remain server-authoritative.

---

## Executive summary

| Vector | Verdict | Action this night |
|---|---|---|
| PayMe webhook authenticity | **Secure by API confirm** (IPN HMAC unused by design) | Added test: forged notify + failed API lookup does not mark paid |
| Checkout price tampering | **Secure** | Re-asserted underpay is rejected |
| SafePay / escrow release | **Secure for bank payout** (admin-only); wallet unlock is event + 36h | Asserted seller cannot `mark-paid` |
| Ticket file upload | **Secure** (magic bytes + MIME + size) | Script-as-PDF rejected; `RELAX_PDF` ignored when `DEBUG=False` |
| Receipt upload | **Was weak — hardened** | Same magic/MIME/extension checks as tickets |
| Ticket PDF IDOR | **Secure** (seller / paid buyer / staff / signed `dl`) | Asserted stranger download returns 403 and no `%PDF` bytes |
| Public PII | **Mostly secure — reservation email leak closed** | Public ticket detail strips `reservation_email` / `reserved_by` |
| JWT | **Secure server-side**; residual XSS if tokens sit in `localStorage` | Documented; no token-lifetime change |
| Phone / email APIs | **Secure** | Extra omit-phone tests on guest checkout and seller upgrade |

---

## 1. Payment & escrow (PayMe)

### 1.1 Webhook endpoints

| Route | Auth | Role |
|---|---|---|
| `POST /api/payments/webhook/payme/` | `AllowAny` (PSP callback) | Fulfillment |
| `POST /api/payments/webhook/` (Grow) | `AllowAny` | Log-only, no order mutation |
| `POST /api/payments/mock-success/` | `DEBUG` + owner | Dev only |
| `POST /api/users/payments/payme/init/` | Order owner / guest | Start sale |

**Outcome — webhook body is not trusted.** `payme_webhook` persists the raw body, binds merchant order id + stored sale/transaction id + currency/amount, then calls `confirm_payme_sale_status()`. Finalize runs only when that API returns `status == 'success'`.

**Outcome — IPN HMAC is not the live control.** `verify_payme_webhook_request` documents that Standard Seller accounts do not get `merchant_password`; MD5 helpers exist but are unused. Authenticity is the PayMe API lookup. Enabling HMAC blindly would risk dropping valid Apple Pay / wallet notifies.

**Outcome — replay.** Duplicate success notifies are idempotent (`test_payment_scary_cases`). A notify that fails API confirm leaves the order `pending_payment` (new overnight test).

**Hardened:** none on the verify algorithm (would break wallet IPNs). **Tested:** `test_forged_payme_webhook_without_api_confirm_does_not_pay`.

### 1.2 Buyer cannot set the charge amount

`create_order` / guest checkout compute `_checkout_expected_total` from `ticket.asking_price` (or accepted offer) + fees/coupons. Client `total_amount` must match or the request is rejected. `Order.total_amount` is read-only on the serializer. PayMe `sale_price` is taken from the persisted order, not the browser.

`asking_price` is read-only on `TicketSerializer`; sellers send `listing_price`.

Production blocks `confirm-payment` when PayMe webhook confirmation is required (`PAYME_REQUIRE_WEBHOOK_CONFIRMATION=True` if `not DEBUG`).

**Tested:** underpay does not create a cheap `pending_payment` row (existing + overnight).

### 1.3 SafePay / escrow release

There is **no ticket-scan / QR gate** in this codebase. Release is:

1. Order → `paid` creates a locked `SellerPayout` / wallet credit.  
2. After **event end + 36 hours**, status can become `eligible` (lazy promotion on wallet/admin/dashboard reads).  
3. **Bank transfer** is only `POST /api/users/admin/payouts/{id}/mark-paid/` (staff). Admin mark-paid still refuses locked / pre-36h rows.

Sellers have GET-only `/api/users/me/wallet/`. They cannot trigger a bank payout.

**This matches “admin before funds leave the platform.”** It does **not** match “scan the ticket at the gate before unlock.” Adding a scan product is a product decision, not a silent security patch.

**Tested:** seller `mark-paid` → 403; payout stays untransferred. Existing payout suite still passes.

---

## 2. Ticket & file upload

### 2.1 `/sell/new` → `POST /api/users/tickets/`

Already required: authenticated seller, 5MB cap, PDF/JPEG/PNG magic bytes, extension whitelist, UUID storage path, Cloudinary `type=authenticated` in production.

**Hardened tonight**

- `RELAX_PDF_UPLOAD_VALIDATION` is honored **only when `DEBUG=True`**. A leaked env flag cannot loosen production MIME checks.  
- Receipts (`receipt_file`) now use `validate_receipt_upload()` — magic bytes, MIME-aligned types, `.pdf/.jpg/.jpeg/.png`, 15MB cap — in both the view and `TicketSerializer`.

**Tested:** HTML/script named `.pdf` rejected; text/plain + `%PDF` rejected with relax-on + DEBUG-off; HTML receipt rejected; anonymous upload 401/403. Existing mobile upload suite still passes.

### 2.2 Private files / IDOR

Download is `GET /api/users/tickets/{id}/download_pdf/`: seller, staff, paid buyer, or HMAC `dl` token (ticket+order, max 90 days). Query `?email=` alone is rejected. Response is `Content-Disposition: attachment`. Public serializers never return raw Cloudinary/S3 URLs.

Receipts: seller/staff only.

**Residual:** integer ticket IDs yield 403 (exists, no access) vs 404 (missing). That leaks existence, not file bytes. Changing to uniform 404 would break existing clients/tests; left as-is.

**Dev-only residual:** `DEBUG` + no Cloudinary serves `/media/` without the download ACL.

**Tested:** other user PDF/receipt → 403 and body is not a PDF. Existing IDOR suite still passes.

---

## 3. Authentication, authorization & PII

### 3.1 JWT

Backend: access 60 minutes, refresh 7 days, rotate + blacklist. Dual auth: HttpOnly cookies and `Authorization: Bearer`.

Frontend still mirrors tokens in `localStorage` (`tradetix_jwt_access` / `tradetix_jwt_refresh`) for Safari/webview fallback. **Residual:** XSS can steal the Bearer copy. Cookies alone would be the next hardening step (out of scope for this API-first pass).

### 3.2 PII

| Data | Public? | Gate |
|---|---|---|
| Seller username | Yes | Listing |
| Email / phone / bank | No | Owner profile or staff admin |
| Guest email/phone | Order creator only | Not on dashboard list serializer |
| `reservation_email` / `reserved_by` | **Was on ticket retrieve** | **Stripped tonight** unless seller/staff |

**Hardened:** `TicketSerializer.to_representation` pops reservation PII for non-owners.

**Tested:** public detail/list contain no seller email, phone, bank JSON, or guest reservation email. Profile GET as user B does not return user A.

### 3.3 Phone / email validation (direct API)

Serializers already required email + `normalize_required_phone` on register, guest checkout, and profile PATCH (cannot blank phone). PayMe init requires buyer phone.

**Added tests**

- Guest checkout with `guest_phone` omitted (not just blank) → 400, no order.  
- Upgrade-to-seller omit / blank `phone_number` → 400.

---

## 4. Code hardened

| File | Change |
|---|---|
| `backend/users/secure_ticket_storage.py` | `validate_receipt_upload()` |
| `backend/users/views.py` | Receipt check before copy; `relax_pdf` requires `DEBUG` |
| `backend/users/serializers.py` | Receipt validator; strip reservation PII on public ticket JSON |
| `backend/users/tests/test_security_audit_overnight.py` | New defensive suite |
| `backend/users/tests/test_contact_field_validation.py` | Omitted guest phone |
| `backend/users/tests/test_upgrade_to_seller_bank_details.py` | Omitted/blank upgrade phone |

---

## 5. Tests run (self-verification loop)

**Pass 1:** overnight + contact + upgrade (30) — 1 profile-shape failure, fixed.  
**Pass 2:** overnight + contact + upgrade (30) — OK.  
**Pass 3:** overnight + mobile upload + IDOR/tamper + payout API (33) — OK.

Representative assertions:

- Forged PayMe notify + `payme_sale_not_found` → order stays `pending_payment`.  
- Underpay → no cheap order.  
- Seller cannot mark payout transferred.  
- Disguised ticket/receipt files → 400.  
- Stranger download → 403, no file bytes.  
- Public ticket JSON has no reservation/seller PII.

---

## 6. Residual risks / recommended next work

1. **Ticket-scan escrow (product):** wallet unlock is still time-based. If policy requires a scan or admin before *any* seller credit becomes available, add an explicit state — do not treat the 36h timer as a scan.  
2. **IPN signature as defense-in-depth:** only if PayMe confirms Standard Seller can send a stable HMAC on card *and* wallet notifies.  
3. **Remove Bearer from `localStorage`** once cookie auth covers all mobile WebViews.  
4. **Guest order receipt `?email=`:** prefer the same signed `dl` token used for ticket PDFs.  
5. **Uniform 404 on unauthorized download** if existence probing becomes a concern.  
6. **Confirm production env:** `RELAX_PDF_UPLOAD_VALIDATION=false`, `USE_CLOUDINARY=true`, `DEBUG=false`.

---

## 7. What this audit did not do

- No live PayMe production webhook replay against real charges.  
- No Cloudinary ACL probe on the live CDN (requires prod credentials).  
- No XSS payload campaign against the React app.  
- No ticket-scan product implementation.
