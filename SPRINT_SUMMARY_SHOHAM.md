# Sprint Summary Report — Full-Stack & QA (March 29, 2026)

Prepared for Shoham. This document summarizes what was implemented, where it lives, and how to verify it after deploy.

## 1. Off-by-one pricing / float alignment

- **Backend:** `users/pricing.py` now exposes `list_price_checkout_amounts()`, `payment_amounts_match()`, and returns **`Decimal`** from `expected_buy_now_total()` and `expected_negotiated_total_from_offer_base()` (no float math on comparisons).
- **Views:** `create_order`, `guest_checkout` (negotiated path), and `payment_simulation` validate amounts with **`decimal_money()`** and **`payment_amounts_match()`** (±0.02 ILS). `payment_simulation` computes `base_dec`, `fee_dec`, `total_dec` in one place and no longer uses `total - base_price` floats for negotiated service fee.
- **Frontend:** `CheckoutModal.jsx` list-price flow uses **whole shekels from `getTicketPrice(ticket)`** × quantity as the base subtotal (matches Django ticket face rounding), then `buyerChargeFromBase()` — removed `Math.round(ticketBaseNum)` drift for list checkout.
- **UI:** Totals continue to display with `.toFixed(2)` where breakdown objects are used.

## 2. “Become a Seller” onboarding

- **Already present:** `User` model fields (`phone_number`, `payout_details`, `accepted_escrow_terms`), `POST /api/users/me/upgrade-to-seller/`, `BecomeSellerModal`, and `/sell` CTA **`הפוך למוכר עכשיו`** with `refreshProfile` on success. No schema change required this sprint.

## 3. Auto-migrations on Render

- **`build_render.sh`** already runs `python manage.py migrate --noinput` after `pip install`.
- **`render.yaml`:** Comment updated to document that the API build runs migrate via `build_render.sh` (no shell access needed on Render).

## 4. Mobile responsiveness

- **`CheckoutModal.css`:** Narrow screens — full-width modal, stacked checkout buttons, min 48px touch targets, wrapping price rows, smaller negotiated badge text.
- **`Sell.css`:** Full-width listing card, stacked upgrade actions, larger submit button, stacked seating rows and missing-event actions.
- **`Dashboard.css`:** Full-width `checkout-btn`, word-break on offer titles, card overflow guard.
- **`App.css`:** Already had safe-area padding on `main`.

## 5. PDF-only uploads & size cap

- **`TicketViewSet.create`:** Keeps **5MB** cap, **`.pdf` extension**, `%PDF` magic, and `application/pdf` MIME when strict.
- **`_upload_mime_allowed`:** In strict mode, explicitly rejects obvious non-PDF families (`image/*`, `text/*`, etc.) before other checks.

## 6. Double-click / duplicate actions

- **Checkout:** Guard on `handlePaymentSubmit` if `loading`; info step `infoStepBusy`; PDF downloads guarded with `pdfDownloadBusyId`; success PDF buttons disabled while a download runs.
- **Event offer:** `offerSubmitting` on “שלח הצעה”.
- **Negotiation:** `offerMutationBusy` disables accept/reject/counter during any mutation; accept shows “מאשר…”.
- **Dashboard:** `rejectingOfferId`, `checkoutOpeningRef` to avoid opening checkout twice; reset ref on modal close.

## 7. N+1 / query performance

- **`ProfileOrderSerializer`:** `build_profile_orders_serialization_context()` batches ticket ids → one `Ticket` query; `get_tickets` / `get_status_timeline` use `profile_tickets_by_id`. Same pattern applied to **`OrderSerializer.get_tickets`** with DB fallback if no cache.
- **`user_profile` & `user_activity`:** Use the new context builder; listings use `select_related('event')`, `Prefetch('orders', ...)` for order counts, and **`build_listing_primary_order_map()`** for sold-ticket order lookup.
- **`ProfileListingSerializer`:** Uses listing order map when provided; `get_order_count` uses prefetched `orders`.
- **`OfferViewSet`:** `select_related(..., 'parent_offer', 'counter_offer')`.
- **`TicketViewSet`:** Already used `select_related('event', 'seller')`.

## 8. Playwright E2E (`e2e/seller-onboarding-live.spec.js`)

- Sets **mobile viewport** (390×844).
- Asserts **checkout total row** in the modal matches `expectedBuyerTotalFromBase(OFFER_BASE)` on info and payment steps.
- After confirm-payment, asserts success and **`[data-e2e="checkout-success-pdf"]`**, then **`waitForEvent('download')`** and filename ends with `.pdf`.

## Deploy checklist

1. Merge/push to **`main`**.
2. Render API service rebuild runs **`build_render.sh`** → **migrations apply automatically**.
3. Smoke: register → upgrade seller → list → offer → accept → checkout totals match → PDF download.
4. Optional: `npx playwright test seller-onboarding-live.spec.js` with `E2E_WEB_URL` / `E2E_API_URL` pointing at production or staging.

## Note on “wait for Render”

Deployment timing depends on your Render queue and build minutes. After push, confirm the API deploy log shows **“build_render.sh finished OK”** and no migration errors.
