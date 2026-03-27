# SafeTicket — Morning Audit Report (Final Comprehensive Mandate)

**Date (workspace):** 2026-03-27  
**Production API:** `https://safeticket-api.onrender.com/api`

---

## Executive summary

| Area | Status | Notes |
|------|--------|--------|
| Cloudinary upload | **OK** | `Invalid Signature` resolved after credential updates on Render; URL vs split-env priority is in `settings.py`. |
| PDF download (buyer) | **Fixed in code** | Production returned HTTP 500 on `download_pdf` for multi-ticket orders; root causes addressed: **signed Cloudinary delivery URL** for raw PDFs + **`Order.covers_ticket()`** for int/str-safe `ticket_ids` JSON. |
| Marketplace conflicts | **Reviewed + documented** | Offers, pairs, and race paths traced in `users/views.py` (`create_order`, `payment_simulation`, `OfferViewSet.accept`). |
| Security | **Hardened** | `download_pdf` errors generic when `DEBUG=False`; ticket API URLs documented earlier. |
| Performance | **Improved** | `EventViewSet` list queryset uses `select_related('artist')`. |

---

## 1. Infrastructure & Cloudinary

### Verified (production QA JSON, prior run)

- `GET /users/events/` → 200  
- Seller login (`qa_bot`) → OK  
- Upload 2 PDFs → **201** (no `Invalid Signature`)  
- Fake PDF rejection → **400**  
- Admin approve ×2 → **200**  
- Buyer register + checkout → **201**  
- Profile orders → **1** order  

### Code (already in repo)

- `CLOUDINARY_URL` parsing, BOM strip, split-env priority when all three `CLOUDINARY_*` are set.  
- `CLOUDINARY_SIGNATURE_ALGORITHM`: `sha1` (default) or `sha256`.  

### Download fix (this audit)

1. **`Order.covers_ticket(ticket_id)`** (`users/models.py`): treats **FK** `ticket_id` and **`ticket_ids` JSON** consistently (int/str). Fixes buyers who purchased **quantity > 1** where the second ticket id might not have matched `ticket.pk in list` if types differed.  

2. **`download_pdf`** (`users/views.py`): when `USE_CLOUDINARY`, fetch bytes via **`cloudinary.utils.cloudinary_url(..., resource_type='raw', sign_url=True)`** + `requests.get`, because **`FileField.read()`** (unsigned CDN URL inside django-cloudinary-storage) can **403** on restricted/signed-delivery setups.  

3. **Response headers**: ASCII-safe `Content-Disposition` filename to avoid encoding errors.  

4. **Errors**: `logger.exception` server-side; client gets **generic** message unless `DEBUG=True`.  

5. **`user_can_access_ticket_pdf`** (`users/serializers.py`): uses **`order.covers_ticket`**.  

---

## 2. Complex marketplace logic (“conflict tests”) — code verification

### A. Negotiation (offers) → checkout price

- **`OfferViewSet.accept`**: sets offer `accepted`, rejects other pending offers on same ticket, sets checkout window.  
- **`create_order`**: if `offer_id` present, loads `Offer` with `buyer=request.user`, `status='accepted'`, validates `total_amount` vs offer + 10% fee within tolerance.  
- **Other buyers** still see **listing** price from ticket/event APIs (offer acceptance does not rewrite `Ticket.asking_price` for the world); checkout without `offer_id` uses normal **ceil(unit×1.10)** validation.  

*Automated multi-session offer E2E was not re-run in this workspace; behavior is enforced in `create_order` + `Offer` model.*

### B. “Sell in pairs” (`split_type` → `pairs`)

- **`create_order`** (group path): maps Hebrew / English split types; if `split_key == 'pairs'` and `order_quantity % 2 != 0` → **400** `"Tickets can only be bought in pairs"`.  
- Single-ticket legacy path applies the same rule.  

### C. Last-ticket race / overselling

- **`create_order`**: `transaction.atomic()` + **`select_for_update()`** on tickets in group purchase; re-checks status after lock.  
- **`payment_simulation`**: same pattern (see `payment_simulation` block with `select_for_update`).  

*True millisecond parallel load tests require a load harness (e.g. threaded requests); DB locking is implemented in code.*

---

## 3. Security & media privacy

| Check | Result |
|-------|--------|
| `GET /download_pdf/` without auth / wrong user | **403** (existing IDOR checks). |
| Anonymous ticket detail | `pdf_file_url`: **null**, `has_pdf_file`: **true** (no raw storage URL to anonymous). |
| Logs on download failure | **Exception server-side**; client message **sanitized** when `DEBUG=False`. |
| `DEBUG` on Render | **Should be `False`** (`render.yaml` / dashboard). |

---

## 4. Performance & UX (“Loading Events”)

- **Backend:** `EventViewSet.get_queryset()` now **`select_related('artist')`** to cut queries for list/detail that touch artist.  
- **Frontend:** No exact string `"Loading Events"` found; event lists use standard `loading` state + `eventAPI.getEvents()`. Slowness is often **network** or **`release_abandoned_carts()`** on hot paths—monitor in production if needed.  

---

## 5. Deliverables: Cloudinary / API URLs from last successful upload path

From a successful QA run **before** download fix, ticket **download** URLs were **API-relative** (secure pattern), e.g.:

- `https://safeticket-api.onrender.com/api/users/tickets/<id>/download_pdf/`

**Raw** `res.cloudinary.com` URLs are **not** exposed on ticket serializers for unauthorized users (see launch serializer changes).

---

## 6. Git / deploy

- Fixes committed as: **`fix: PDF download Cloudinary signed URL + Order.covers_ticket`** (see git log).  
- Push: `git push origin main` (resolve auth locally if needed).  
- **Do not** leave `RENDER_API_KEY` in env when running `morning_launch_qa.py` unless you intend to trigger a deploy every run.  

---

## 7. Conflicts simulated (summary table)

| Scenario | Mechanism in code | Expected behavior |
|----------|-------------------|---------------------|
| Offer accepted price only | `create_order` + `offer_id` | Total must match offer + fee tolerance. |
| Buy 1 on pairs listing | `split_key == 'pairs'` | **400** pairs error. |
| Two buyers, one ticket left | `select_for_update` + status re-check | Second transaction should fail validation. |
| Multi-ticket order download | `Order.covers_ticket` + signed read | Buyer can download **each** ticket id in order. |

---

*End of Morning Audit Report.*
