# TradeTix Overnight QA & Security Audit Report

**Role:** Senior QA Automation Engineer / Security Penetration Tester  
**Scope:** Full-stack TradeTix (SafeTicket) — Django API + React (Vite) SPA  
**Date:** 2026-07-14  
**Branch audited:** `main` (with staged hardening fixes from this run)  
**Focus:** Mobile app-like UX, reverse-funnel auth, escrow/pricing integrity, uploads, concurrency

---

## Executive summary

The marketplace shows **solid escrow foundations**: checkout totals are recomputed server-side from `PLATFORM_BUYER_SERVICE_FEE_RATE`, reserves/orders use `select_for_update`, ticket PDFs are gated by seller/staff/paid-buyer, and uploads enforce size + MIME + magic bytes.

The reverse funnel (lazy registration on `/sell`) is **functionally sound** for the happy path but had a **recoverability gap** after auth/upgrade when upload failed (modal closed too early). That is fixed in this run.

Highest remaining residual risks are **JWT in `localStorage` (XSS → account takeover)**, **IL face-value enforcement relying on self-declared price equality** (no independent receipt requirement), and **polyglot/malicious PDF content** that still passes magic-byte checks (expected for PDF marketplaces; mitigated by Cloudinary private storage + auth downloads).

---

## 1. Components & flows tested

### 1.1 Frontend

| Component / flow | Path | Aspects checked |
|---|---|---|
| Sell (listing form) | `frontend/src/pages/Sell.jsx` | Validation, reverse funnel gate, `listingSnapshotRef`, draft persistence, Bit/Bank completion handoff |
| SellCompletionModal | `frontend/src/components/SellCompletionModal.jsx` + CSS | Z-index, overlay dismiss, touch targets, iOS zoom, body scroll lock, Bit vs Bank required fields |
| Sell styles | `frontend/src/pages/Sell.css` | Overflow-x, 16px inputs, 44–48px controls, checkbox targets |
| Navbar | `frontend/src/components/Navbar.css` | Sticky z-index, Sell CTA touch size |
| CheckoutModal | `frontend/src/components/CheckoutModal.css` | Z-index 10000 parity with SellCompletion |
| EventDetails + maps | `EventDetailsPage.jsx/.css`, Menora/Stadium maps | Sticky map/filter stacking vs navbar |
| Floating WhatsApp | `FloatingWhatsApp.css` | Z-index vs modals |
| Pricing constants | `frontend/src/constants/pricing.js` | Client fee display vs server authority |
| API client / auth | `frontend/src/services/api.js` | Bearer storage, CSRF header, token refresh |

### 1.2 Backend

| Flow | Path | Aspects checked |
|---|---|---|
| Registration | `UserRegistrationSerializer` | Role forced to `buyer` (ignores client `role`) |
| Upgrade to seller | `upgrade_to_seller` + `UpgradeToSellerSerializer` | Escrow acceptance, Bit vs Bank field requirements |
| Ticket create | `TicketViewSet.create` + `TicketSerializer` | Authz (seller-only), qty clamp 1–10, file validation, IL legal declaration |
| Price update | seller price PATCH path in `views.py` | Positive price enforcement (hardened) |
| Checkout / orders | `create_order`, guest checkout | `expected_buy_now_total` vs client `total_amount` |
| Reserve concurrency | `TicketViewSet.reserve` + tests | Second buyer blocked |
| Fees | `users/pricing.py` | Fee rates from Django settings only |
| PayMe webhook | `payme_views.py` / `payments.py` | HMAC verify, sandbox bypass rules |
| PDF access | `user_can_access_ticket_pdf` | Seller / staff / paid buyer only |

### 1.3 Automated verification run this session

- `users.tests.test_ticket_price_bounds` — **PASS** (negative/zero listing rejected)
- `users.tests.test_concurrency_guards` — **PASS**
- `users.tests.test_launch_offer_validation` — **PASS**

---

## 2. Findings by severity

### HIGH

#### H1 — Reverse funnel: modal closed before upload completed (recoverability / partial state)
**Status:** **Fixed this run**  
**Before:** `handleCompletionSubmit` called `setCompletionOpen(false)` *before* `executeTicketUpload`. On network failure after `upgrade_to_seller`, the user was already a seller, the modal was gone, and error UX was weak.  
**After:** Modal stays open until `listingSnapshotRef` is cleared (upload success). Overlay/Escape/`×` disabled while `saving`.  
**Files:** `Sell.jsx`, `SellCompletionModal.jsx`

#### H2 — Negative / zero listing prices accepted by API serializer
**Status:** **Fixed this run**  
**Before:** `TicketSerializer.original_price` / `listing_price` had **no `min_value`**. A crafted multipart request could create ≤0 prices (UI blocked this; API did not). Seller price-update path treated any truthy string including `"-1"` as valid.  
**After:** `min_value=Decimal('0.01')` on serializer fields; price update rejects `<= 0`.  
**Files:** `serializers.py`, `views.py`, `test_ticket_price_bounds.py`

---

### MEDIUM

#### M1 — JWT access/refresh tokens in `localStorage`
**Evidence:** `frontend/src/services/api.js` (documented mobile/iOS Safari strategy).  
**Risk:** Any XSS on the SPA origin exfiltrates Bearer tokens → full account takeover (incl. seller payout mutation after auth). HttpOnly cookies alone are harder on split-origin SPA, but residual XSS risk remains.  
**Mitigation ideas:** harden CSP; minimize `dangerouslySetInnerHTML`; rotate refresh; consider BFF cookie bridge if same-site ever possible.

#### M2 — IL anti-scalping is self-declared face value
**Evidence:** Sell uploads set `original_price` and `listing_price` to the **same** seller-entered amount. Receipt is **optional**. Serializer only ensures `listing_price <= original_price` for IL.  
**Risk:** Seller can claim any “face” price without proof; legal/compliance gap (not a direct fee-tamper bug).  
**Recommendation:** Require receipt for IL listings and/or separate face vs asking inputs with admin OCR review.

#### M3 — Partial reverse-funnel account creation without listing
**Dry-run:** Register succeeds → login fails/network drop → orphan buyer account exists; payout not yet set.  
Upgrade succeeds → upload fails → user is seller with payout details but no listing (now retriable from open modal if still on page).  
**Recommendation:** Idempotent “resume listing” after remount; persist file metadata or warn clearly that files must be re-selected after navigation (sessionStorage draft intentionally omits File blobs).

#### M4 — PayMe webhook verbose logging
**Evidence:** `payme_views.py` logs full incoming payload.  
**Risk:** PII / payment metadata in Render logs; signature secret mishandling harder but log retention grows blast radius.  
**Recommendation:** Redact payload keys matching secret/token/signature/email/phone.

#### M5 — Sticky stacking: EventDetails map `z-index: 1000` ≈ Navbar
**Evidence:** `EventDetailsPage.css` sticky map at 1000; Navbar sticky at 1000; mobile menu/drawer higher (1100+); SellCompletion/Checkout at **10000**.  
**Risk:** On event pages, sticky map can compete visually with navbar; filters intentionally stack above map. Modals correctly win. Not a user trap for SellCompletion, but EventDetails mobile chrome can feel cluttered.

---

### LOW

#### L1 — Navbar Sell CTA was &lt; 44px on mobile
**Status:** **Fixed** — `min-height: 44px` desktop + mobile.  
**File:** `Navbar.css`

#### L2 — Completion modal inputs / radios needed clearer mobile affordances
**Status:** **Fixed** — `font-size: 16px` on completion inputs; payout radio + escrow checkbox min-height 44px; body scroll lock + Escape handling.  
**File:** `SellCompletionModal.css/.jsx`

#### L3 — Checkbox hit areas on Sell remain 20×20 CSS boxes
Wrapped labels help, but raw `.checkbox-input` is 20px. Acceptable if label provides larger hit area; still below Apple HIG for the control alone.

#### L4 — Israeli ID number lacks checksum (Luhn-like)
`UpgradeToSellerSerializer` only checks digit length 5–9. Enables fake but plausible IDs.

#### L5 — Filename uniqueness only (not content hash)
Duplicate PDF *content* with different filenames can be uploaded (business rule, not RCE).

#### L6 — `RELAX_PDF_UPLOAD_VALIDATION`
Dangerous if ever `true` in production (encrypted/broken PDFs coerce to qty=1). Confirm Render env stays `"false"` (`render.yaml` already sets false).

---

## 3. Security deep-dive results

### 3.1 Auth bypass / reverse funnel

| Attack | Result |
|---|---|
| Client sends `role: 'seller'` on register | **Blocked** — `UserRegistrationSerializer.create` hardcodes `role='buyer'` |
| Skip payout fields, call `createTicket` as buyer | **Blocked** — `TicketViewSet.create` requires `role == 'seller'` |
| Skip escrow checkbox | **Blocked** client + `accepted_escrow_terms` server validation |
| Switch to Bit and leave bank fields empty | **OK** — bank inputs unmounted (HTML `required` not fired); server Bit branch does not require bank fields |
| Login path without phone | Client requires phone; Bit path requires matching confirm |

**Session tokens:** Bearer in localStorage/session bootstrap; Authorization header attached by axios interceptor. Not leaked in URL. Residual = XSS (M1).

### 3.2 File upload security

| Control | Present? |
|---|---|
| Max size 5MB tickets | Yes (`TicketViewSet.create`) |
| Extension allowlist `.pdf/.jpg/.jpeg/.png` | Yes |
| Magic bytes PDF/JPEG/PNG | Yes (`_upload_is_ticket_attachment`) |
| Blocked MIME families (`text/`, `video/`, …) when not relaxed | Yes |
| Randomized storage names / private Cloudinary fetch | Yes (secure storage path) |
| Executable / HTML upload as ticket | **Rejected** (magic + MIME) |
| 50MB file | **Rejected** (5MB) |
| Polyglot PDF with JS | **Residual** — PDFs are files-for-download, not executed in app; buyers open externally |

### 3.3 Payload tampering (pricing / quantity / fees)

| Tamper | Backend behavior |
|---|---|
| Client `BUYER_SERVICE_FEE_PERCENT` | **Ignored** — fee from `settings.PLATFORM_BUYER_SERVICE_FEE_RATE` via `users/pricing.py` |
| Client `total_amount` lower than expected | **Rejected** within ±0.02 via `payment_amounts_match` / `expected_buy_now_total` (orders use **server_total**) |
| Client `available_quantity` = 999 | **Clamped** to `max(1, min(10, …))`; PDF count must match |
| Client `asking_price` write | **Read-only** on serializer; derived from listing/original |
| Negative `listing_price` | **Now rejected** (was gap → fixed) |

**Verdict:** Checkout fee/total tampering is **not viable**. Quantity inflation is constrained. Listing price is seller-chosen (as expected) but bounded &gt; 0.

### 3.4 Escrow / double-sell

- Order create + reserve paths use `transaction.atomic()` + `select_for_update()`.
- Concurrency tests confirm second buyer gets Hebrew conflict.
- Escrow unlock ≈ 36h after event end (`compute_payout_eligible_date`).

---

## 4. Mobile UX deep-dive

| Check | Result |
|---|---|
| Horizontal overflow on Sell | `overflow-x: hidden` on container; mobile wrap overrides for checkboxes |
| Touch targets ≥ 44px | Mostly good on Sell/Checkout/Maps; **Navbar Sell CTA fixed**; radio labels enlarged in completion modal |
| Z-index SellCompletion vs Navbar/WhatsApp | Completion **10000** &gt; WhatsApp 1100 &gt; Navbar 1000 — **no trap** after fixes |
| Sticky filters vs map vs nav | Designed stacking on EventDetails; map z=1000 can feel heavy under/near navbar |
| iOS auto-zoom | Sell inputs `font-size: max(16px, 1rem)`; completion inputs now explicit **16px** |
| Virtual keyboard | Completion uses `max-height: min(92dvh, …)` + scroll; body scroll locked while open |
| Overlay dismiss while saving | **Disabled** (was unsafe) |

---

## 5. `listingSnapshotRef` / Bit–Bank / E2E state

### Data flow (trace)

1. Guest/buyer fills listing + files → `handleSubmit` validates → `captureListingSnapshot()` stores `{ formData (incl. File refs), uploadMethod }` in **`useRef`**.
2. Opens `SellCompletionModal`.
3. On submit: validate completion → optional register/login → CSRF → profile → `upgradeToSeller` if needed → **`executeTicketUpload(snapshot)`**.
4. On success: clear draft + `listingSnapshotRef = null` → close modal (new behavior).

### Survival rules

| Event | Snapshot survives? |
|---|---|
| Modal open/close without remount | Yes (ref) |
| Component unmount / navigate away | **No** — ref lost; session draft keeps form fields **without files** |
| Network drop mid-upload (after this fix) | Modal stays; retry possible while File refs still in memory |
| Tab crash | Lost (draft may restore seats/price only) |

### Bit vs Bank

- UI **conditionally renders** bank vs Bit fields (not `display:none` with `required`).
- Server `UpgradeToSellerSerializer.validate` enforces mutually exclusive requirements.
- Hidden bank values are blanked in `buildUpgradePayload` for Bit.

---

## 6. Autonomous edge-case scenarios (≥5) — dry-runs

### EC1 — Two buyers click Buy simultaneously on last seat
**Expectation:** Only one reserve succeeds.  
**Code:** `select_for_update` on reserve / order create; `test_reserve_second_buyer_gets_hebrew_conflict`.  
**Result:** **Pass.**

### EC2 — Upload 50MB “ticket.pdf”
**Expectation:** Reject.  
**Code:** `MAX_PDF_SIZE = 5 * 1024 * 1024`.  
**Result:** **Pass.**

### EC3 — Negative listing price via Burp (UI bypassed)
**Expectation:** Reject.  
**Before:** Fail (serializer allowed). **After fix + test:** **Pass.**

### EC4 — Rename `malware.html` → `ticket.pdf` without PDF magic
**Expectation:** Reject on magic/MIME.  
**Result:** **Pass** (fails `_upload_is_ticket_attachment`).

### EC5 — Register as seller by POSTing `role=seller` then upload
**Expectation:** Still buyer; upload PermissionDenied until upgrade with payout/escrow.  
**Result:** **Pass.**

### EC6 — Lower `total_amount` on guest checkout to skip 5% fee
**Expectation:** Order uses `server_total` / mismatch reject.  
**Result:** **Pass** (server authority).

### EC7 — Reverse funnel: auth OK, Cloudinary upload 502
**Before:** Modal closed; confusing state. **After:** Modal remains with retry message.  
**Residual:** User is seller; re-submit as authenticated seller also works if they close and resubmit form.

### EC8 — Inflate `available_quantity` to 10 with 1 PDF page
**Expectation:** Auto-split mode requires page_count == qty (strict) or 1:1 files.  
**Result:** **Pass** when `RELAX_PDF_UPLOAD_VALIDATION=false`.

### EC9 — Seller edits price to `-5` after listing
**After fix:** Rejected with Hebrew error. **Pass.**

### EC10 — Click overlay during completion submit
**After fix:** Ignored while `saving`. **Pass.**

---

## 7. Code fixes applied (staged)

| Change | Why |
|---|---|
| Keep `SellCompletionModal` open until upload success | Recover network / Cloudinary failures without losing funnel context |
| Disable overlay/Escape/close while `saving`; body `overflow: hidden` | Prevent dismiss/trapping issues; reduce accidental abort |
| `TicketSerializer` `min_value=0.01` on prices | Stop negative/zero API listings |
| Seller price update rejects `<= 0` | Close same hole on edit |
| `test_ticket_price_bounds.py` | Regression lock |
| Navbar Sell CTA ≥ 44px (incl. mobile override) | Touch target compliance |
| Completion modal 16px inputs + larger radio/checkbox rows | iOS zoom + touch |

**Git:** changes are **staged** (not committed/pushed — commit when you wake if desired).

```
backend/users/serializers.py
backend/users/views.py
backend/users/tests/test_ticket_price_bounds.py
frontend/src/pages/Sell.jsx
frontend/src/components/SellCompletionModal.jsx
frontend/src/components/SellCompletionModal.css
frontend/src/components/Navbar.css
```

---

## 8. Architectural & UX recommendations

1. **Persist reverse-funnel resume token** server-side (draft listing row) so Files need not survive SPA remounts.
2. **CSP + XSS hygiene** — highest ROI against JWT-in-localStorage risk.
3. **Require IL receipt** for `pending_approval` listings; admin checklist for face vs asking.
4. **Israeli ID checksum** validation on upgrade.
5. **Redact PayMe webhook logs**; alert on repeated `bad_signature`.
6. **Unify modal z-index tokens** (`--z-modal: 10000`, `--z-nav: 1000`, `--z-sticky-map: 900`) to avoid EventDetails/Nav collisions.
7. **Disable double-submit** on Sell publish with request idempotency key.
8. **E2E Playwright** for reverse funnel: guest → Bit → upload failure → retry → success.
9. **Content hashing** for uploaded tickets to flag duplicate file abuse.
10. Consider **httpOnly refresh cookie** on API domain + short-lived memory access token for reduced XSS blast radius.

---

## 9. What looked healthy (keep)

- Seller-only ticket creation after role upgrade  
- Server-side fee math (`pricing.py`)  
- Checkout total authority + ±0.02 tolerance  
- Reserve/order row locks  
- Ticket PDF ACL (no public Cloudinary URL in list serializers)  
- Upload magic-byte + size + extension triad  
- August/Menora seed idempotency on Render start (out of scope but production ops OK)

---

## 10. Suggested next actions when online

1. Review staged diff → commit → deploy (so production gets price bounds + modal recoverability).  
2. Confirm Render `RELAX_PDF_UPLOAD_VALIDATION=false`.  
3. Spot-check on iPhone Safari: `/sell` guest reverse funnel Bit path + Menora event sticky map under filters.  
4. Schedule XSS/CSP work as a separate hardening PR.

---

*End of overnight audit. Fixes are staged locally; say the word if you want them committed and pushed to `main`.*
