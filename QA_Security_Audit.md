# TradeTix QA & Security Audit

**Date:** 26 August 2026  
**Scope:** React (Vite) frontend + Django REST Framework + PostgreSQL  
**Method:** Static review of views/viewsets, serializers, payment webhook path, ticket file storage, seller/buyer UI flows, slug routing, and existing automated tests. Immediate defects found during the review were patched in the same change set.

This is a **code audit**, not a live penetration test. No exploits or attack payloads were written or executed.

---

## 1. What was tested

### 1.1 Object-level permissions (tickets & profile)

| Surface | Result |
|---|---|
| `TicketViewSet.get_queryset` | Public list is limited to `active`, `taken`, `sold`, and `pending_payout` for **upcoming** events. Authenticated sellers also see their own rows (same date filter). `pending_approval` listings are not enumerable by other users. |
| `TicketViewSet.update` / `destroy` | Owner check: non-owners receive 403. `seller` is read-only on `TicketSerializer`; create always binds `seller=request.user`. |
| `update_ticket_price` | Owner + `active` + pending-payment lock. Rejects `<= 0`. |
| `TicketViewSet.retrieve` | Uses the same queryset as list. Another buyer cannot retrieve a `pending_approval` ticket (404). Public retrieve of **sold** listings is allowed by design (marketplace “taken” UI). |
| `user_profile` GET/PATCH | `IsAuthenticated`. Always the **current** user — there is no `user_id` lookup, so IDOR on profile is not present. PATCH is limited to `first_name`, `last_name`, `phone_number`. |
| `upgrade_to_seller` | Authenticated; writes payout details on `request.user` only. |
| `OfferViewSet.get_queryset` | Scoped to `buyer=user` **or** `ticket__seller=user`. Retrieve/list cannot see strangers’ offers. |
| `create_order` | Server recomputes totals (`_apply_order_pricing_fields` / `expected_buy_now_total`). Client `total_amount` underpay is rejected (`users.tests.test_checkout_idor_tamper`). Quantity `< 1` rejected. Inventory uses `select_for_update`. |

**Pass** for ownership of mutations. See §5 for residual information-disclosure notes on the public ticket list.

### 1.2 Payment security (PayMe webhook / IPN)

Reviewed: `backend/users/payme_views.py` (`payme_webhook`), `backend/users/payments.py` (`verify_payme_webhook_request`), `backend/services/payme_service.py` (`confirm_payme_sale_status`), `confirm_order_payment`.

| Control | Result |
|---|---|
| CSRF / auth on webhook | `AllowAny`, CSRF-exempt POST (required for PSP callbacks). |
| Cryptographic signature | **Not used.** Seller PayMe accounts do not receive `merchant_password`. Comments in `verify_payme_webhook_request` state HMAC/MD5 is not a security control. |
| Payload binding | Rejects mismatched `merchant_order_id`, stored `payme_transaction_id` / sale refs, currency, and amount (agorot) when amount fields are present. |
| Server-to-server confirm | After binding, the view **always** calls `confirm_payme_sale_status` (`get-sales`, fallback `get-transactions`). Fulfillment runs only if PayMe returns `found` and `status == success`. |
| API unavailable | 503 — does not mark paid. |
| Sale not found / non-success | Does **not** finalize. Returns 200 with `finalized: false` so PayMe is less likely to retry forever. |
| Client mock ack | `confirm_order_payment` is `AllowAny`, but `PAYME_REQUIRE_WEBHOOK_CONFIRMATION` is **True whenever `DEBUG` is False**. Production clients cannot mock-ack. `payment_simulation` 404s unless `DEBUG`. |

**Verdict:** A spoofed webhook body **cannot** mark tickets paid without a matching live PayMe sale. Authenticity is API lookup, not HMAC. That architecture is sound **if** `PAYME_CONFIRM_SUCCESS_VIA_API` stays true and seller API credentials are not leaked. See §5 for operational follow-ups.

### 1.3 File security (ticket PDFs)

| Control | Result |
|---|---|
| Storage path | `ticket_pdf_upload_to` uses `tickets/pdfs/{uuid}{ext}` — original filenames are discarded. |
| Cloudinary | Authenticated `type` + signed fetch only (`secure_ticket_storage.py`). API serializers never emit raw CDN URLs. |
| Download ACL | `user_can_access_ticket_pdf`: seller, staff/superuser, or paid/completed order (user **or** matching `guest_email`). Anonymous download requires a **signed `?dl=` token** bound to ticket + order. `?email=` alone is rejected. |
| Receipts | Seller/staff only — not buyers. |
| Local `DEBUG` | `urls.py` serves `MEDIA_URL` from disk **only when `DEBUG` and not Cloudinary**. UUID names reduce guessing; this must never be enabled in production. |

**Pass** for production Cloudinary path. Guessing `/media/tickets/pdfs/<uuid>.pdf` is not a practical IDOR if Cloudinary authenticated delivery is correctly configured in the cloud account (see §5).

### 1.4 Seller flow (`TicketUploadWizard` + PDF verification / seating)

| Item | Result |
|---|---|
| Wizard shell | Presentational only; listing state lives on `Sell.jsx` so step changes do not drop `File` objects. |
| Price | Client rejects empty / non-finite / `<= 0`. Serializer `min_value=0.01`. Backend tests: `test_ticket_price_bounds.py`. |
| Zone dropdown | Options come from `venue_detail.sections` or static venue maps. **Fix:** skip section rows with a missing `id` so `"undefined"` is not POSTed as `venue_section`. |
| Admin verification modal | Per-ticket seats + global first-seat auto-increment. Backend `parse_seat_assignments` ignores malformed items. **Fix:** `incrementSeatLabel` no longer emits `NaN` when offset is invalid. |
| PDF upload | Size cap 5MB, MIME + magic bytes, unique filenames, page-count vs quantity for split PDFs. |

### 1.5 Buyer flow (Event Details, cart, checkout)

| Item | Result |
|---|---|
| Sticky mobile buy bar | Shown at `max-width: 768px`. Footer / WhatsApp FAB / sell FAB already padded via `body.has-event-mobile-buy-bar`. Ticket list already has extra bottom padding. **Fix:** bar is **hidden while “סינון ומיון” is expanded** so filters are not covered (`z-index: 900` vs filter panel `z-index: 40`). |
| Canonical slug | After `getEvent`, if `event.slug !== eventKey`, the page `navigate(..., { replace: true })`. |
| `add_to_cart` | Analytics only; inventory hold is `TicketViewSet.reserve` then `create_order` / guest checkout. |
| Checkout totals | Server-side pricing; IDOR underpay tests exist. |
| Timeouts | Axios default 60s; order create 120s. List fetches abort at 28s. **Fix:** checkout maps `ECONNABORTED` / `ERR_NETWORK` to a Hebrew connection message (previous regex used a typo `ecconn`). |
| Terms | `accepted_terms` required on create_order / guest checkout. |
| Shabbat | 403 `SHABBAT_RESTRICTION` handled before generic session-expired UX. |

### 1.6 Routing & Hebrew → English slug migration

| Path | Result |
|---|---|
| `resolve_event_by_identifier` | Numeric PK, current `slug`, then `legacy_slug`. |
| SPA HTML (`spa_index_view`) | If identifier is id or `legacy_slug`, **HTTP 301** to `/event/<ascii-slug>`. Exceptions fall through to SPA HTML (not 500). |
| API retrieve | Same resolver. Existing test: `test_legacy_hebrew_slug_still_resolves`. |
| Event tickets nested action | Uses **unscoped** `Event.objects.all()` (past events OK). |
| **Bug found** | `EventViewSet.get_object` previously used `get_queryset()`, which filters `date__gte=now`. **Past events 404’d on `GET /api/users/events/<slug>/`**, so the Event Details “הופעה זו עברה” branch never ran. **Fixed** — retrieve/SEO resolve against all events. Regression: `test_api_retrieve_past_event_by_slug_and_legacy`. |

Unknown slugs still 404 on the API (correct). The SPA catch-all serves `index.html` rather than a hard 404 for unknown `/event/...` paths; React then shows “אירוע לא נמצא”. That is a product/SEO choice, not a 500.

### 1.7 Error handling & validation

| Check | Result |
|---|---|
| Negative / zero listing price | Rejected client + serializer + `update_ticket_price`. |
| Missing sell fields | Event, price, packages/files validated before submit. |
| Checkout missing identity | Dedicated inline form, not a raw stack trace. |
| Quantity | 1–10 on tickets; order quantity ≥ 1. |
| CSRF on cross-origin checkout | Documented exemption + JWT Bearer; HTML 403 pages are not toasted as raw HTML. |

### 1.8 Automated checks run with this change set

- Django: `users.tests.test_event_seo` (legacy slug + new past-event retrieve).
- Frontend: `adminTicketSeating.test.js`; production `npm run build`.

---

## 2. Fixes included in this change set

1. **Past / legacy event API 404** — `EventViewSet.get_object` no longer filters to upcoming-only events.
2. **Mobile buy CTA vs filters** — sticky bar unmounts while the mobile filter/sort panel is open; filter panel keeps safe-area padding.
3. **Seat auto-increment** — invalid offsets no longer produce `NaN` seat strings sent to the admin seating API.
4. **Zone dropdown** — sections without an `id` are omitted from the Sell wizard payload.
5. **Checkout network timeouts** — Axios abort/network codes map to a user-facing Hebrew retry message.

---

## 3. Critical / architectural items that need manual review

These are **not** one-line patches. They need product + infra owners.

### 3.1 PayMe: no HMAC, fulfillment via seller API credentials

Webhook authenticity equals “can we see this sale with **our** `seller_payme_id` / API key?” That is correct for this PSP account type, but:

- Anyone can POST to the webhook URL (expect 403/200 `finalized: false` without a real sale).
- If seller API keys leak, an attacker who also knows `payme_transaction_id` could theoretically confirm sales they control — protect secrets in Render env, rotate on suspicion.
- Amount check is skipped when the payload omits price (Apple Pay / some wallets). Binding still requires stored sale/transaction id + live `get-sales` success.
- `PayMeWebhookLog` stores raw bodies. Confirm retention, access control (staff only), and PII/PCI minimization.

**Manual check:** In production, POST a forged webhook for a real `pending_payment` order and confirm it stays unpaid; then pay once and confirm a single finalize (idempotent).

### 3.2 Cloudinary “authenticated” delivery must be account-true

Code fetches `type=authenticated` only. If the Cloudinary preset is accidentally **public/upload**, UUID paths can still be fetched from the CDN without going through `download_pdf`.

**Manual check:** Copy a `pdf_file.name` from Django admin and request the unsigned Cloudinary URL. Expect 401/404, not the PDF.

### 3.3 Public marketplace includes sold / pending_payout rows

Event ticket lists expose sold inventory (gray “taken” seats). That leaks that a given seat sold and the seller’s user id / username. Confirm this is an accepted product choice vs. aggregating taken seats without seller identifiers.

### 3.4 `DEBUG` media serving

Local disk `MEDIA_URL` is only wired when `DEBUG=True` and Cloudinary is off. Confirm production `DEBUG=False` and `USE_CLOUDINARY=True` on Render. Never enable Django static media serving in prod.

### 3.5 Staff PDF access

Any Django `is_staff` user can download any ticket PDF via the API ACL. Treat staff accounts as highly privileged; prefer 2FA on Django admin and a small staff allowlist.

### 3.6 SPA 404 vs 301 split across hosts

301 for Hebrew slugs runs on the **Django** host that serves `index.html`. If a CDN or a second frontend host serves the SPA without that view, bookmarks may skip 301 and rely on the React `replace` navigation + API `legacy_slug` lookup. Confirm `tradetix.co.il` HTML is always Django (or the Node SEO inject server with the same redirect).

### 3.7 `confirm_order_payment` remains AllowAny

Production is gated by `PAYME_REQUIRE_WEBHOOK_CONFIRMATION`. If that flag is ever turned off in prod (mis-set env / `DEBUG=True` on Render), mock ack + `payment_confirm_token` become a second payment path. Add a deploy check: `DEBUG` must be false; the flag must be true.

---

## 4. Recommendations for scaling securely

1. **WAF / rate limit** the PayMe webhook and checkout mutation throttles (already scoped). Alert on spikes of `payme_sale_not_found` / `order_binding_failed`.
2. **Idempotency keys** on `create_order` (client key stored on `Order`) to survive double-submit and mobile retries without duplicate pending rows.
3. **Private object storage** (S3/GCS with bucket policies denying public ACL) as a Cloudinary backup; keep the app as the only ACL gate.
4. **Field-level encryption** or vault for `payout_details` / bank fields at rest; restrict serializer output to the owning user (already the case for profile).
5. **Structured audit log** (user, ticket id, action, IP, request id) for download_pdf, price edits, admin approve, and payouts — separate from PayMe payload dumps.
6. **Do not log full card/PSP payloads** in application logs; hash sale ids in info logs (partial hashing already exists in places).
7. **Read replicas** for event/ticket list; keep `select_for_update` checkout on primary only.
8. **Row-Level Security** in PostgreSQL is optional defense-in-depth later; DRF queryset scoping is the current control. Do not add RLS until a dedicated DB role model exists.
9. **CSP / Helmet** on the SPA plus `Content-Disposition: attachment` on PDFs (already set) to reduce inline XSS via uploaded files.
10. **Periodic job:** replay `payme_webhook_replay` for stuck `pending_payment` (code exists) with paging and Slack/ops alerts — do not rely on IPN alone at volume.

---

## 5. Residual risk summary

| Severity | Item | Status |
|---|---|---|
| High if misconfigured | Cloudinary public delivery / `DEBUG` media | Config review required |
| High if flag flipped | Client `confirm_order_payment` in production | Flag is correct in settings; monitor env |
| Medium | Webhook has no HMAC (by PSP design) | Mitigated by get-sales |
| Medium | Sold listings visible on public event pages | Product decision |
| Low | SPA unknown event paths return HTML 200 | SEO/ops choice |
| Fixed | Past-event API 404 | Patched |
| Fixed | Mobile CTA covering filters | Patched |
| Fixed | NaN seats / missing section ids / checkout timeout copy | Patched |

---

## 6. Sign-off

Immediate, straightforward defects from this audit were fixed and covered by regression tests where practical. Payment fulfillment, PDF ACL, and ticket/profile ownership look **intentionally designed** rather than missing. Remaining work is **operational verification** (Cloudinary privacy, production `DEBUG`/`PAYME_*` flags, webhook load tests) rather than additional naive permission checks in viewsets.
