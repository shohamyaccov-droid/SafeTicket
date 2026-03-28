# 1-Hour Security & UI Fix Sprint — Report

**Date:** 2026-03-28  
**Scope:** Phases 1–3 per mandate: media/Cloudinary fixes, checkout/payment integrity, guest-offer IDOR, public PII scrub, ticket details scoping, tests, and deployment notes.

---

## Phase 1 — UI & media

### 1.1 Artist / event card images (API)

**Issue:** Relative or non-HTTPS image URLs broke cards after DRY image handling.

**Change:** In `backend/users/serializers.py`:

- Added `cloudinary_signed_https_image_url()` and `resolved_image_url()`.
- `ArtistSerializer`, `ArtistListSerializer`, `EventSerializer`, and `EventListSerializer` now prefer **signed `https://` Cloudinary** URLs (`resource_type='image'`, `sign_url=True`, `secure=True`) using `_public_id_variants` from `admin_pdf_url.py`.
- Falls back to `absolute_file_url()` for local/non-Cloudinary storage.

### 1.2 Frontend CLS & URL resolution

**Files:** `frontend/src/utils/formatters.js`, `frontend/src/pages/Home.css`

- `getFullImageUrl` now builds relative media URLs against `VITE_API_URL` (stripping `/api`) or production default `https://safeticket-api.onrender.com`, not hardcoded localhost only.
- **Event / artist card wrappers:** `aspect-ratio` (16/9 for events, 1/1 for artists), `min-height` / `max-height`, gradient placeholder background, `display:block` on images to stabilize layout (CLS).

### 1.3 Admin PDF 401 (Cloudinary raw)

**File:** `backend/users/admin_pdf_url.py`

- First attempt for each public_id variant: `cloudinary.utils.cloudinary_url(..., resource_type='raw', type='upload', sign_url=True, secure=True)` so admin preview/download gets a valid signed HTTPS URL before falling back to API metadata + older logic.

---

## Phase 2 — Security & marketplace integrity

### 2.1 Payment / inventory (two-step checkout)

**Model:** `backend/users/models.py` — `Order.status` adds `pending_payment`; adds `held_ticket`, `held_quantity`, `pending_offer` (migration `0031_order_pending_payment_and_hold.py`).

**Flow:**

1. **`create_order` / `guest_checkout`:** Validates pricing and availability, **holds** inventory (group rows → extended reservation; single qty 1 → reservation; single qty &gt; 1 → decrement `available_quantity` + `held_ticket`/`held_quantity` + row stays active/reserved as before), creates `Order` with `status='pending_payment'`, `pending_offer` when negotiated. **Does not** call `_apply_order_pricing_fields`, **does not** send receipt email, **does not** mark tickets `sold` (except the intentional partial-row hold semantics).

2. **`POST /api/users/orders/<id>/confirm-payment/`** (`confirm_order_payment` in `backend/users/views.py`, wired in `backend/users/urls.py`): After **mock / webhook** validation, finalizes sale (`sold`), runs `_reject_pending_offers_for_ticket_ids`, sets `paid`, runs `_apply_order_pricing_fields` (escrow clock), sends receipt email.

**Confirmation gate:**

- If `MOCK_PAYMENT_WEBHOOK_SECRET` is set in the environment, request must send matching `payment_secret` (body) or `X-Payment-Secret` header.
- Otherwise **development:** `mock_payment_ack: true` in JSON body.

**Abandonment:** `release_abandoned_carts()` cancels stale `pending_payment` orders (same timeout window as cart reservations) and restores group reservations / held quantities.

**Helpers added in `views.py`:** `_restore_order_held_inventory`, `_release_pending_payment_group_reservations`, `_guest_offer_email_matches`, `_reserve_rows_for_pending_checkout`, `_verify_reservations_fresh`, `_finalize_group_sale_ticket_rows`.

### 2.2 Guest offer IDOR

- **`guest_checkout`:** If an accepted `offer_id` is used, `guest_email` must match `negotiated_offer.buyer.email` (case-insensitive). Otherwise **403**.
- **`payment_simulation`:** For anonymous negotiated flow, requires `guest_email` (or `email`) matching the offer buyer’s email.

### 2.3 Public PII scrub (`TicketListSerializer`)

**File:** `backend/users/serializers.py`

- Removed `reserved_at`, `reserved_by`, `reservation_email` from public list payloads.
- Added boolean `is_reserved_slot` so UI can still show “in cart” without leaking emails or user IDs.

### 2.4 `TicketViewSet.details` information disclosure

**File:** `backend/users/views.py`

- `details` now uses `self.get_object()` so access matches `get_queryset()` (marketplace + own listings), not arbitrary ticket IDs.

### 2.5 Guest checkout `listing_group_id`

- `GuestCheckoutSerializer` includes optional `listing_group_id`; view uses `order_data` or `request.data`.

---

## Phase 3 — Frontend checkout wiring & QA

### 3.1 API & checkout UI

**Files:** `frontend/src/services/api.js`, `frontend/src/components/CheckoutModal.jsx`

- `orderAPI.confirmPayment(orderId, data)` added.
- After successful `createOrder` / `guestCheckout`, client calls `confirmPayment` with `{ mock_payment_ack: true, guest_email? }`.
- `payment_simulation` payload includes `guest_email` for guests when an offer is involved.

### 3.2 Tests updated

- `test_autonomous_marathon_qa.py` — guest flows call confirm-payment after pending order creation; assertions allow “reserved” messaging where relevant before final sale.
- `test_premium_offer_e2e.py` — purchase test confirms payment; `@override_settings` raises offer throttle limit for isolated tests.
- `test_ultimate_bid_flow.py` — class-level throttle override to avoid 429 on `OfferViewSet` reads.

**Command run (subset):**  
`python manage.py test test_autonomous_marathon_qa test_premium_offer_e2e test_ultimate_bid_flow` — **OK**.

**Note:** Other repo scripts (e.g. `qa_price_integrity.py`, `morning_launch_qa.py`) that POST only to `/orders/` without confirm will need a follow-up `POST .../confirm-payment/` step to complete purchases against the new API contract.

### 3.3 Git & Render

- **Git:** Commit and push from your machine with your credentials; this environment attempted logical completion of code changes only.
- **Render:** Deploy by pushing to the connected branch; set optional `MOCK_PAYMENT_WEBHOOK_SECRET` on the API service before relying on non-mock confirmation in shared environments.

---

## Operational checklist

| Item | Action |
|------|--------|
| Database | Apply migration `0031_order_pending_payment_and_hold` on all envs (`migrate`). |
| Production mock pay | Set `MOCK_PAYMENT_WEBHOOK_SECRET` and have the client (or webhook worker) send the secret; remove reliance on `mock_payment_ack` in prod. |
| SPA | Rebuild frontend so `formatters.js` + `CheckoutModal` ship together. |
| Legacy scripts | Update any automation that assumed immediate `paid` orders. |

---

## Files touched (summary)

| Area | Paths |
|------|--------|
| Models / migration | `backend/users/models.py`, `backend/users/migrations/0031_*.py` |
| Views / checkout | `backend/users/views.py`, `backend/users/urls.py` |
| Serializers | `backend/users/serializers.py` |
| Admin PDF | `backend/users/admin_pdf_url.py` |
| Frontend | `frontend/src/services/api.js`, `frontend/src/components/CheckoutModal.jsx`, `frontend/src/utils/formatters.js`, `frontend/src/pages/Home.css` |
| Tests | `backend/test_autonomous_marathon_qa.py`, `backend/test_premium_offer_e2e.py`, `backend/test_ultimate_bid_flow.py` |

---

*End of report.*
