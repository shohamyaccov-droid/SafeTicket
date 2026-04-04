# TradeTix / SafeTicket — Security Audit Report

**Audit type:** Pre-launch application security review (API, authz, financial flows, file access).  
**Scope:** Django REST backend (`backend/users/`), storage configuration, admin surfaces.  
**Date:** 2026-04-05  

This document lists controls verified, gaps found, and changes applied in this pass.

---

## 1. Broken Object Level Authorization (BOLA / IDOR)

| Area | Status | Notes |
|------|--------|--------|
| **TicketViewSet.list/retrieve** | **Verified** | `get_queryset()` returns active marketplace tickets (upcoming events) ∪ authenticated seller’s own tickets (same upcoming filter). Guessing another user’s non-public ticket ID yields **404** for retrieve when not in queryset. |
| **TicketViewSet.details** | **Verified** | Uses `self.get_object()` → scoped to `get_queryset()` (docstring/commit history: previously used raw `Ticket(pk)`; now aligned with retrieve). |
| **TicketViewSet.update / destroy** | **Verified** | Explicit `ticket.seller != request.user` → **403** before mutation. |
| **TicketViewSet.download_pdf** | **Verified + hardened** | IDOR checks: seller, paid/completed buyer (order covers ticket), or guest with matching `email` + paid order. **Change:** Django **staff/superuser** may download (parity with serializer gate `user_can_access_ticket_pdf`). |
| **TicketViewSet.download_receipt** | **Verified** | Seller or staff/superuser only. |
| **Ticket reserve / release_reservation** | **Verified (residual risk)** | Uses `get_object_or_404(Ticket, pk=pk)` outside listing queryset. Functionally gated by status checks; may leak *existence* via different error shapes vs strict 404. **Recommendation:** scope lookup to public queryset or normalize errors to generic 404 for unauthenticated probes. |
| **update_ticket_price** | **Verified** | Loads ticket by ID but enforces `ticket.seller == request.user` and `status == active`. |
| **OfferViewSet.get_queryset** | **Verified** | Default: offers where user is buyer OR ticket seller; `received` / `sent` narrow further. |
| **OfferViewSet.accept** | **Fixed** | Previously loaded offer by primary key globally, then returned **403** for non-participants (offer ID enumeration). **Now:** loads offer through **`self.get_queryset().select_for_update()`** so non-participants get **404**. Recipient checks unchanged. |
| **OfferViewSet.reject / counter** | **Verified** | Use `self.get_object()` → queryset-scoped. |
| **create_order** | **Verified** | Ticket/group locked with `select_for_update`; `total_amount` checked against server `expected_buy_now_total` / negotiated offer total; self-purchase blocked. |
| **confirm_order_payment** | **Verified** | Requires user match for authenticated orders or `guest_email` match; secret/token/webhook gate; pricing finalized via `_apply_order_pricing_fields`. |
| **Custom admin API routes** | **Verified** | `admin_*` handlers use `_admin_staff_or_superuser()` (staff or superuser). |

---

## 2. Financial & Transactional Integrity

| Control | Status | Notes |
|---------|--------|--------|
| **Authenticated checkout** | **Verified** | `create_order` recomputes expected totals from `ticket.asking_price` (or grouped reference) and `quantity`; negotiated path uses `Offer.amount` + `expected_negotiated_total_from_offer_base`. Mismatch → **400**. |
| **Guest checkout — negotiated** | **Verified** | Email must match offer buyer; total matched to negotiated expectation. |
| **Guest checkout — buy-now** | **Fixed (critical)** | Previously `Order.total_amount` could be taken from client (`order_data.get('total_amount', ticket.asking_price)`), allowing **underpayment** vs true fee-inclusive total. **Now:** if `not negotiated_offer`, `total_amount` is rejected unless it matches `expected_buy_now_total(ticket.asking_price, order_quantity)`. |
| **Payment simulation endpoint** | **Verified** | Recalculates totals server-side; compares submitted amount with `payment_amounts_match`. |
| **OrderSerializer fees** | **Verified** | Buyer/seller fee fields read-only on serializer; breakdown applied after payment in `_apply_order_pricing_fields`. |
| **OfferSerializer.amount** | **Verified** | Validated & quantized server-side; offer line amounts drive accepted-offer checkout (not rebinding to a client “total” that bypasses offer). |

---

## 3. File Security (Tickets: PDF / Images)

| Topic | Status | Notes |
|-------|--------|--------|
| **Public API exposure** | **Verified** | `TicketSerializer` / list serializers do not expose raw Cloudinary URLs to unauthorized users; `pdf_file_url` uses authenticated download route when `user_can_access_ticket_pdf`. |
| **download_pdf transport** | **Verified** | Bytes loaded server-side (`_download_ticket_pdf_bytes` / storage) and streamed after authz — not a blind redirect to a static public URL for anonymous users. |
| **Cloudinary `raw` uploads** | **Operational** | Delivery URLs depend on Cloudinary account/settings. **Recommendation:** keep resources **private** / **strict** transformations, rely on signed/admin API for staff, and avoid embedding long-lived public `raw` URLs in any public JSON. |
| **Guest download** | **Verified** | Requires `email` query matching a paid order covering that ticket (documented IDOR defense). |

---

## 4. XSS & SQL Injection

| Topic | Status | Notes |
|-------|--------|--------|
| **SQL injection** | **Verified (ORM)** | Business logic uses Django ORM / `filter(pk=…)` patterns — parameterized queries. **Recommendation:** never add raw SQL with string-concatenated user input. |
| **Stored XSS via API** | **Mitigated by client** | Marketplace is React; text fields rendered as text nodes reduce DOM XSS. **Recommendation:** if server-rendered HTML emails/templates include user names/event text, keep auto-escaping (Django templates) or explicit escaping. |
| **Reflected XSS in API** | **Low** | JSON APIs return structured data; avoid reflecting unsanitized HTML in error messages. |

---

## 5. Admin & Authentication Security

| Topic | Status | Notes |
|-------|--------|--------|
| **Django `/admin/`** | **Verified (framework)** | Standard Django admin; requires staff/superuser login. |
| **SPA admin verification** | **Verified** | `AdminVerificationPage` redirects non-staff users; API uses `_admin_staff_or_superuser`. |
| **DEBUG / test flags** | **Checklist** | `DEBUG` must be **`False`** on production hosts. `RELAX_PDF_UPLOAD_VALIDATION` must be **`False`** unless tightly scoped testing. |
| **JWT_RESPONSE_BODY_TOKENS** | **Noted** | Mobile-friendly bearer tokens in JSON; ensure HTTPS-only and short-lived access tokens on production. |

---

## 6. Change Summary (This Commit)

1. **guest_checkout:** Server-side validation of buy-now `total_amount` against `expected_buy_now_total` (closes client price manipulation).  
2. **OfferViewSet.accept:** Offer row locked only if visible in **`get_queryset()`** for the current user (BOLA / enumeration hardening).  
3. **TicketViewSet.download_pdf:** Allow **staff/superuser** download for operational/support alignment with serializer rules.  

---

## 7. Residual Risks & Launch Checklist

- [ ] Confirm **Render** env: `DEBUG=False`, `SECRET_KEY` rotated, `MOCK_PAYMENT_WEBHOOK_SECRET` set for non-mock gateways, `RELAX_PDF_UPLOAD_VALIDATION=False`.  
- [ ] Review **Cloudinary** privacy / signed URL policy for `raw` ticket assets.  
- [ ] Optional: unify **reserve** / **release** ticket lookup with marketplace queryset + generic 404.  
- [ ] Rate limits: already present on auth/offer scopes — monitor 429s and tune if needed.  

---

*End of report.*
