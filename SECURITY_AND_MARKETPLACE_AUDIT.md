# SafeTicket — Security & Marketplace Audit

**Auditor role:** Senior Cybersecurity Auditor & Marketplace Product Manager  
**Scope:** Static and logical review of the SafeTicket codebase (backend Django/DRF, key frontend flows), plus industry benchmark research.  
**Constraint:** No code was modified as part of this engagement; findings reference repository paths as of the audit date.

---

## Executive summary

SafeTicket implements meaningful **IDOR defenses** on ticket PDF downloads and order receipts (explicit owner checks), **negotiation state machines** with row locks for accept/counter, and **scoped rate limiting** on the offers API. However, the **payment path is not cryptographically or PSP-bound to order creation**: authenticated and guest checkout endpoints mark orders `paid` on trust that payment already succeeded. A **guest-path flaw** allows **accepted offers to be consumed by anyone who knows (or guesses) the `offer_id`**, because buyer identity is not verified for guests. Public listings may expose **cart-hold contact identifiers** (`reservation_email`) to unauthenticated users. Escrow is modeled in the database (`payout_status`, `payout_eligible_date`) but **operational payout to sellers** must be validated separately—there is no substitute for regulated payment flows, KYC, and chargeback handling.

---

## 1. Security & vulnerability sweep

### 1.1 Severity legend

| Level | Meaning |
|-------|---------|
| **Critical** | Exploitable logic that can steal inventory, funds, or high-value assets with no insider access |
| **High** | Serious confidentiality issue, privilege bypass, or fraud enabler in realistic conditions |
| **Medium** | Meaningful weakness, misconfiguration, or partial exposure |
| **Low** | Defense-in-depth, hygiene, or limited blast radius |

### 1.2 Critical

| ID | Title | Location | Description |
|----|--------|----------|-------------|
| **C-1** | **Orders marked paid without payment-processor proof** | `backend/users/views.py` — `create_order` (approx. lines 862–1195), `guest_checkout` (approx. lines 1355–1624) | Both flows persist `Order` with `status='paid'` and mutate ticket inventory inside `transaction.atomic()`, with comments stating payment was *already processed*. There is **no server-side verification** of a payment intent, capture, idempotency key, or signed webhook from a PSP before committing inventory. **Impact:** Any client that can satisfy price/quantity validations can obtain tickets without paying, in any deployment where these endpoints are reachable. |
| **C-2** | **Guest checkout / payment simulation: accepted offer not bound to buyer** | `backend/users/views.py` — `guest_checkout` (`negotiated_offer = Offer.objects.get(id=offer_id, status='accepted')`, approx. lines 1362–1372), `payment_simulation` (guest branch: `Offer.objects.get(id=offer_id, status='accepted')` without buyer check, approx. lines 1304–1310) | Authenticated `create_order` correctly requires `buyer=request.user` for offer validation (approx. lines 876–882). **Guests do not.** **Impact:** An attacker who learns a victim’s **accepted** `offer_id` (enumeration, leak, browser history, shared link) can complete guest checkout with **their own** email/phone, pay the *negotiated* total (or bypass payment if C-1 applies), and **receive the tickets**—denying the legitimate negotiating buyer. |

### 1.3 High

| ID | Title | Location | Description |
|----|--------|----------|-------------|
| **H-1** | **Public exposure of reservation holder identifiers** | `backend/users/serializers.py` — `TicketListSerializer` `Meta.fields` includes `reserved_by`, `reservation_email`, `reserved_at` (approx. lines 463–487); consumed by `backend/users/views.py` — `EventViewSet.tickets` → `TicketListSerializer` (approx. lines 2288–2445) | Marketplace event pages return **who is holding a cart** (including `reservation_email`) to unauthenticated clients when a ticket is `reserved`. **Impact:** Email (PII) and user id leakage; harassment, phishing, or targeting. |
| **H-2** | **Guest PDF and receipt access keyed on guessable factors** | `backend/users/views.py` — `TicketViewSet.download_pdf` (`guest_email` query param, approx. lines 1993–2003), `order_receipt` (guest path with `guest_email`, approx. lines 723–747) | Authorization is **not** a signed, rotating magic link. **Impact:** Anyone who knows (or guesses) a buyer’s **email** and **ticket id** / **order id** can download the PDF or JSON receipt. Sequential integer IDs increase feasibility. Email-only gates are weaker than industry “magic link to buyer inbox.” |
| **H-3** | **`payment_simulation` exposed to anonymous callers** | `backend/users/views.py` — `payment_simulation` (`@permission_classes([AllowAny])`, approx. lines 1199–1352); `backend/users/urls.py` — `path('payments/simulate/', …)` (line 51) | Even if order endpoints were fixed, leaving a **public** “simulate payment” endpoint in production aids abuse reconnaissance and keeps unsafe patterns one misconfiguration away from live traffic. |

### 1.4 Medium

| ID | Title | Location | Description |
|----|--------|----------|-------------|
| **M-1** | **`TicketViewSet.details` bypasses listing queryset scoping** | `backend/users/views.py` — `details` action (approx. lines 1954–1962): `ticket = get_object_or_404(Ticket, pk=pk)` then full `TicketSerializer` | Standard `retrieve` uses `get_queryset()` (active + own listings). **`details` does not**, so **any** ticket primary key may return rich metadata (seller id, seat data, event nesting) even when not “on sale,” depending on ticket state. **Impact:** Information disclosure; assists targeting and mapping of inventory. |
| **M-2** | **JWT blacklist setting without blacklist app** | `backend/safeticket/settings.py` — `SIMPLE_JWT` includes `'BLACKLIST_AFTER_ROTATION': True` (approx. line 328); `INSTALLED_APPS` (lines 87–92) lists `rest_framework_simplejwt` but **not** `rest_framework_simplejwt.token_blacklist` | If rotation/blacklist is relied upon for logout/session invalidation, **verify** whether production runs migrations for blacklist tables and whether refresh rotation behaves as intended. Misconfiguration can mean **stolen refresh tokens stay valid** longer than assumed. |
| **M-3** | **Escrow is data-model state, not treasury segregation** | `backend/users/models.py` — `Order.payout_status`, `payout_eligible_date` (approx. lines 417–433); `backend/users/views.py` — `_apply_order_pricing_fields`, `user_activity` promotion `locked` → `eligible` (approx. lines 35–64, 662–667); `backend/users/pricing.py` — `compute_payout_eligible_date` | The codebase tracks **when** a payout may become eligible (24h after event start in pricing helper). **Seller “early cash out”** via API was not observed; however **buyer protection, disputes, chargebacks, and actual fund movement** are outside this model. **Impact:** Regulatory, reconciliation, and trust gaps—not necessarily an IDOR, but a **business-critical** compliance area. |
| **M-4** | **Weak default secrets / debug in settings** | `backend/safeticket/settings.py` — `SECRET_KEY` default `'django-insecure-dummy-key-for-dev'` (line 41), `DEBUG` defaults from env with `'True'` string default (line 44) | Production misconfiguration would have severe impact (error pages, cookie flags, host assumptions). |
| **M-5** | **Rate limiting coverage** | `backend/safeticket/settings.py` — `'DEFAULT_THROTTLE_RATES': {'offers': '10/min'}` (lines 315–318); `backend/users/views.py` — `OfferViewSet` `throttle_scope = 'offers'` (approx. lines 2664–2672) | **Create/accept/reject/counter** share one scoped bucket per user. **10/min** slows naive spam but not distributed abuse. **Accept** is not separately weighted vs **create** (design choice). Other sensitive endpoints (`register`, `login`, `guest_checkout`, `payment_simulation`) were not seen using analogous throttle classes in this review. |

### 1.5 Low

| ID | Title | Location | Description |
|----|--------|----------|-------------|
| **L-1** | **Order API surfaces guest PII** | `backend/users/serializers.py` — `OrderSerializer` includes `guest_email`, `guest_phone` (lines 141–146) | Any response embedding `OrderSerializer` may echo guest contact details to the client; ensure only the purchaser sees their order payload. |
| **L-2** | **Verbose `print` logging in hot paths** | `backend/users/views.py` (many `print(...)` in checkout, events, payment simulation) | Risk of **accidental PII or business data** in centralized logs in production. |
| **L-3** | **Cloudinary delivery posture** | `backend/users/views.py` — `_download_ticket_pdf_bytes`; project doc `backend/MORNING_LAUNCH_REPORT.md` (notes on signed vs public delivery) | API avoids handing out raw URLs in serializers (`TicketSerializer.get_pdf_file_url`), but **storage-level** “authenticated raw” vs **public raw** URLs must be verified in Cloudinary console. Otherwise, **URL entropy** becomes the main control. |
| **L-4** | **Guest checkout schema vs view** | `backend/users/serializers.py` — `GuestCheckoutSerializer` (lines 310–316) lacks `offer_id` / `listing_group_id`; `guest_checkout` reads `listing_group_id` from `serializer.validated_data` (approx. line 1396) | `listing_group_id` may be **`None` for guests** unless the serializer is extended—potential functional gap for grouped listings over the guest path (distinct from security, but affects completeness). |

### 1.6 IDOR focus: PDF tickets

**Positive:** `TicketViewSet.download_pdf` explicitly requires seller, authenticated purchaser with `Order` in `paid`/`completed`, or guest with matching `guest_email` (see `backend/users/views.py`, approx. lines 1964–2009). **Ticket id alone is insufficient** for authenticated users without an order.

**Residual risk:** Guest branch + email guessing (H-2); Cloudinary direct URL if misconfigured (L-3).

### 1.7 Rate limiting & spam (offers)

- **Implemented:** `ScopedRateThrottle` + `'offers': '10/min'` for `OfferViewSet` (`backend/users/views.py`, `backend/safeticket/settings.py`).
- **Gaps:** No dedicated throttles observed for `payment_simulation`, `guest_checkout`, `create_order`, auth endpoints. **Accept** is throttled only by the shared offer bucket.

### 1.8 Escrow manipulation (logic review)

- **Seller forcing early payout:** No user-facing API was identified that sets `payout_status` to `paid` or moves money. Eligibility moves from `locked` to `eligible` when `payout_eligible_date <= now()` during `user_activity` refresh (`backend/users/views.py`, approx. 662–667)—not seller-controlled.
- **Buyer bypassing payment:** **Yes, if C-1 remains**—buyer can obtain `paid` orders without PSP proof.
- **Inventory race:** `create_order` and `guest_checkout` use `select_for_update()` patterns for concurrent sales—**stronger** than average MVPs.

---

## 2. Data exposure (events, artists, listings)

| Surface | Sensitive fields observed | Notes |
|---------|---------------------------|--------|
| `EventViewSet` / `EventListSerializer` | Event name, venue (from catalog), city, date, images | **No** user email/phone on event rows. |
| `ArtistViewSet` | Artist metadata, images | **No** private user PII. |
| `EventViewSet.tickets` → `TicketListSerializer` | **`reservation_email`, `reserved_by`** | **High**—see H-1. |
| `TicketSerializer` (detail / seller flows) | `seller` id, `seller_username`, `seller_is_verified` | Expected for marketplace trust; not full email/phone **unless** combined with other leaks. |
| `UserSerializer` | `email`, `phone_number` | Used for **authenticated profile** (`user_profile`); not identified on public artist/event list endpoints. |

---

## 3. Competitor & industry benchmark (Trust, Safety, UX)

Research synthesized from public-facing descriptions of **TicketSwap**, **StubHub**, **Viagogo**, and common **C2C marketplace** patterns (buyer protection funds, identity, disputes).

### 3.1 Practices leaders emphasize

1. **Strong buyer protection:** Explicit guarantee, refund policy, and/or organizer-backed inventory (e.g. TicketSwap **SecureSwap**, refund protection offerings).
2. **Identity & KYC for sellers (and sometimes buyers):** ID verification, phone verification **signals**, payout account verification (often via PSP such as Stripe Connect).
3. **Pricing & fraud rules:** Caps on mark-up (TicketSwap highlights **max 20%** above original), sanctions on duplicate accounts and bots.
4. **Organizer integrations:** Official transfer / barcode regeneration reduces counterfeit PDF risk.
5. **Dispute resolution:** Structured workflows, evidence upload, SLA, human review for edge cases.
6. **Transparency UX:** Seller history, photo, response time, “verified phone” **badge** without exposing raw PII.
7. **Non-repudiation of payment:** Server-authoritative payment state; no client-trusted “I paid” flag.

### 3.2 Gaps for SafeTicket (product, not exhaustive)

- **No PSP-authoritative payment + webhook idempotency** visible in order creation (blocks parity with any major marketplace).
- **No KYC / seller payout verification** workflow comparable to EU marketplaces.
- **No formal dispute / chargeback** lifecycle beyond PRD mentions.
- **No organizer / primary-ticket API** integration (SecureSwap-class assurance).
- **Trust UX:** Limited public seller reputation, response metrics, historical completion rate (beyond `is_verified_seller`).
- **Fraud:** No device fingerprinting, velocity checks across IPs, stolen-card checks, or listing-level anomaly detection described in code.
- **Bots:** Throttling is minimal outside offers; scraping and enumeration remain plausible.

---

## 4. Prioritized marketplace features (recommended build order)

1. **P0 — Payment integrity:** Replace simulated payment with real PSP (e.g. Stripe PaymentIntents or Tranzila/h local PSP), **server-side-only** transition to `paid`, webhooks with signature verification, idempotency keys, and explicit reconciliation.
2. **P0 — Offer binding for guests:** Secret checkout tokens per accepted offer, or disallow guest negotiated checkout; always bind `Offer.buyer` (including guest accounts or OTP to email before honoring `offer_id`).
3. **P0 — Magic-link delivery:** PDF and receipt access via **single-use signed URLs** emailed to the purchaser; deprecate raw `?email=` on downloads for guests (or add OTP step).
4. **P1 — Remove public reservation PII:** Strip `reservation_email` / `reserved_by` from `TicketListSerializer` public responses; expose only boolean “held” + countdown if needed.
5. **P1 — Hardening `details`:** Align `TicketViewSet.details` authorization with `get_queryset()` or remove the action if redundant.
6. **P1 — Rate limits & abuse:** Global throttles on auth, checkout, contact, alerts; CAPTCHA or proof-of-work on high-risk anonymous endpoints.
7. **P2 — Disputes & escrow ops:** Buyer dispute UI, ops queue, freeze/hold payout on dispute; legal terms aligned with Israeli consumer law (already noted for pricing).
8. **P2 — Seller verification:** Document/KYC for payouts, IBAN verification, tax information where required.
9. **P2 — Secure ticket logistics:** Organizer transfer APIs, barcode refresh, or sealed delivery to reduce PDF resale fraud.
10. **P3 — Trust & community:** Reviews, seller stats, messaging with content moderation, report flow.

---

## 5. SafeTicket vs TicketSwap “secure flow” (summary)

| Dimension | TicketSwap-style flow (public materials) | SafeTicket (observed in code) |
|-----------|------------------------------------------|-------------------------------|
| Payment truth | PSP-settled; platform-mediated release | Client-trusted **“already paid”** path (**C-1**) |
| Ticket validity | SecureSwap / organizer-linked where available | PDF upload + admin verification; no organizer API in scope |
| Buyer protection | Explicit policies, refund add-ons | PRD mentions disputes; implementation depth not audited here |
| Identity | KYC for sellers, phone verification signals | `is_verified_seller`, OTP/email toggles—lighter than full KYC |
| Delivery | Account + email; reduced reliance on shared secrets | Buyer/seller downloads + **guest email query** (**H-2**) |
| Negotiation | (Varies by market) | Rich offer/counter flow with locks—**differentiator**, but must bind identity + payment |

**Bottom line:** SafeTicket’s negotiation and inventory locking show thoughtful **concurrency** design, but **payment and guest-offer binding** must reach **server-authoritative, PSP-backed** parity before the flow is comparable to TicketSwap-class safety claims.

---

## 6. Positive controls (should be preserved in future refactors)

- Explicit **403** on `download_pdf` when unauthorized (`backend/users/views.py`).
- **Owner-first** `order_receipt` queries (`user=request.user` then guest email).
- **`select_for_update()`** usage in purchase paths to mitigate double-selling.
- **Offer accept** recipient checks and automatic rejection of competing pending offers (`OfferViewSet.accept`).
- **Self-bid** prevention on offer creation (referenced in tests and view logic).
- **Scoped throttling** for offers (`ScopedRateThrottle`).

---

## 7. Methodology note

This audit combined: (1) targeted reads of `backend/users/views.py`, `backend/users/serializers.py`, `backend/users/models.py`, `backend/safeticket/settings.py`, `backend/users/urls.py`; (2) semantic search across the repo for payment, offers, escrow, PDFs; (3) public web research on competitor trust/safety narratives. **Dynamic exploitation**, penetration testing, Cloudinary console review, and production config review on Render were **not** executed in this pass.

---

*End of report.*
