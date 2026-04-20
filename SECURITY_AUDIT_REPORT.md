# SafeTicket / TradeTix — Security Audit & QA Sweep Report

**Date:** 2026-04-20  
**Scope:** Backend order/checkout integrity, throttling, guest vs authenticated flows, map integration (section highlighting), and alignment with prior codebase review (transactions, PDF handling, IDOR on downloads).

---

## 1. Vulnerabilities Found & Fixed

### 1.1 Client-controlled `total_amount` persisted on orders (escrow / payment integrity)

**What was wrong**

- `OrderSerializer` accepted `total_amount` from the request body on `create_order`. After the view validated that the client’s number matched the server-computed checkout total, `serializer.save()` still persisted **`validated_data['total_amount']`**, which originated from the client. That is unnecessary trust in duplicated data and weaker defense-in-depth if validation were ever bypassed or refactored incorrectly.
- **`guest_checkout`** validated totals for buy-now and negotiated flows, but then built the `Order` with `total_amount=order_data.get('total_amount', ticket.asking_price)`, again preferring client-supplied values after checks instead of the canonical server total.

**How it could be exploited**

- Any future bug that skipped or mis-ordered validation could persist an attacker-chosen `total_amount`, affecting receipts, downstream payout math, or support workflows that trust the stored order row.
- The guest path’s fallback to `ticket.asking_price` (unit price) for multi-quantity orders could theoretically diverge from true checkout totals if validation were ever incomplete.

**How it was patched**

- **`OrderSerializer`:** `total_amount` is now **read-only** in `Meta.read_only_fields`, so incoming JSON cannot set it; only explicit `serializer.save(..., total_amount=…)` supplies it.
- **`create_order`:** After all locks and business checks, the view computes  
  `server_total = expected_negotiated_total_from_offer_base(negotiated_offer.amount)` or  
  `server_total = expected_buy_now_total(ticket.asking_price, order_quantity)`  
  and calls `serializer.save(..., total_amount=server_total)`.
- **`guest_checkout`:** Replaced client-derived `total_amount` with the same server-side `server_total` rules before `Order.objects.create(...)`.

**Files**

- `backend/users/serializers.py` — `OrderSerializer` read-only `total_amount`
- `backend/users/views.py` — `create_order`, `guest_checkout`

---

### 1.2 Checkout / reserve abuse (rate limiting)

**What was wrong**

- Login/register and offers already used scoped throttles; **create order**, **guest checkout**, **payment simulation**, **confirm payment**, and **reserve** had no dedicated checkout budgets, so automated abuse (spam orders, reservation churn) was only limited by generic user/anon throttles.

**How it could be exploited**

- High-frequency calls to reserve or create pending orders to harass sellers, fill logs, or stress DB locks.

**How it was patched**

- Added **`CheckoutMutationScopedThrottle`** (`scope: checkout`, **60/minute**) on:
  - `create_order`
  - `guest_checkout`
  - `payment_simulation`
  - `confirm_order_payment`
- Added **`CheckoutReserveScopedThrottle`** (`scope: checkout_reserve`, **120/minute**) on `TicketViewSet.reserve`.
- Registered rates in `backend/safeticket/settings.py` under `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`.

**Files**

- `backend/users/throttles.py`
- `backend/users/views.py`
- `backend/safeticket/settings.py`

---

## 2. QA / Logic Review (No Code Defects Found in This Pass)

### 2.1 Upload → listing

- Ticket creation remains seller-authenticated with PDF validation and persistence checks (existing behavior). No change required in this sweep.

### 2.2 Map integration — Section **319**, Row **1**

- **Bloomfield:** `bloomfieldSectionGeometry.js` includes section **319** in the south-tier block lists; `bloomfieldListing.js` maps section numbers to zones and `blockIdFromSectionNumber`. `BloomfieldStadiumMap` highlights via `stableId` / `blockId` derived from listing rows — consistent with listing section **319**.
- **Menora:** Venue geometry lives in **`InteractiveMenoraMap.jsx`** (not a separate `menoraArenaGeometry.js` in this repo); highlighting follows the same pattern as other venue maps (`highlightStableId`).
- **Jerusalem Arena:** `jerusalemArenaGeometry.js` + `EventDetailsPage` selection/`jerusalemMapHighlight` mirror the Bloomfield pattern.

No mismatch was found for section **319** on Bloomfield in static analysis; full visual E2E in a browser was not run in this session.

### 2.3 Checkout → sold / map clears highlight

- Order flow still uses `transaction.atomic()` + `select_for_update()` for contested inventory; listing state transitions on confirm remain in `confirm_order_payment`. Map highlight is driven by active listing selection; sold listings drop out of marketplace queries — **no change** in this pass.

---

## 3. Areas of Confidence (Verified or Strongly Supported by Code)

| Area | Notes |
|------|--------|
| **Double-spend / concurrent purchase** | `create_order` / `guest_checkout` use `transaction.atomic()` and row locks; status re-checked after lock; group purchases lock multiple rows. |
| **Negotiated price** | Offers tied to buyer + `accepted` status; totals derived from `expected_negotiated_total_from_offer_base` / `buyer_charge_from_base_amount`. |
| **Payment simulation** | Compares client `amount` to server `total_dec` before success. |
| **Confirm payment** | Requires webhook secret, mock ack + token, or `payment_confirm_token`; guest must match `guest_email`. |
| **PDF download** | `download_pdf` gated by `user_can_access_ticket_pdf` / signed token (documented anti-IDOR path). |
| **PDF upload** | MIME/magic/extension checks and persistence verification (existing). |
| **Auth brute force** | `auth_login` / `auth_register` scoped throttles (existing). |

---

## 4. Verification

- **Tests:** `python manage.py test users.tests test_night_shift_security` — **21 tests, OK** (after changes).
- **Residual risks (not changed here)**  
  - Duplicate **same PDF file** uploaded under different names (would need content-hash + per-seller/event uniqueness policy).  
  - Any **admin / shell** path that creates `Order` rows must pass `total_amount` explicitly if using `OrderSerializer` for writes.

---

## 5. Git

Changes are committed as a single logical unit: server-authoritative order totals + checkout/reserve throttles + this report.
