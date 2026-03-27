# SafeTicket — Official Pre-Launch Technical Audit

**Date:** 2026-03-27  
**Scope:** Marketplace edge cases, race conditions, state leaks, and admin/moderation flows  
**Test suite:** `backend/launch_edge_case_qa.py`  
**Execution:** `python manage.py test launch_edge_case_qa -v 2` (all tests **PASSED**)

---

## 1. Executive summary

A dedicated edge-case suite was added and executed against the Django backend. During implementation, several **integrity gaps** were identified and **closed in code** before this audit was finalized: offer acceptance did not validate live ticket inventory or concurrent checkout; successful purchases did not systematically invalidate competing pending offers; `create_order` did not reconcile expired cart reservations before charging; guest checkout lacked the same reservation alignment; and admin moderation could only reject **pending verification** listings, not **live** active/reserved fraud cases.

**Current status:** The six automated scenarios below pass; related regression tests (`test_premium_offer_e2e`, `test_offer_api`) also pass.

---

## 2. Tests executed (suite: `launch_edge_case_qa`)

| # | Scenario | Intent | Result |
|---|----------|--------|--------|
| 1 | **Direct buy vs offer** | Buyer B completes purchase before seller accepts Buyer A’s offer; A’s offer must be invalidated; seller accept must fail. | **PASS** — pending offer `rejected` after sale; `POST /offers/{id}/accept/` returns **400** (`no longer pending`). |
| 2 | **Double accept** | Two pending offers on the same ticket; seller accepts first; second accept must fail. | **PASS** — second offer pre-rejected after first accept; second accept returns **400**. |
| 3 | **Admin rejection mid-flow** | Admin rejects a **live** listing (`active`); pending offers invalidated; buyer checkout blocked. | **PASS** — offers + ticket updated; `POST /orders/` returns **400** (`rejected` ticket). |
| 4 | **Reservation / timeout** | Reservation held past TTL; cleanup releases inventory; another buyer can purchase. | **PASS** — `release_abandoned_carts()` releases stale `reserved` rows; subsequent order **201**. *Note: configured timeout is `RESERVATION_TIMEOUT_MINUTES` (10), not 15 — align product copy with config.* |
| 5 | **Pairs bypass (API)** | `split_type = זוגות בלבד`, `quantity=1` via API. | **PASS** — **400** `Tickets can only be bought in pairs`. |
| 6 | **Cross-buyer reservation** | Buyer A reserves; Buyer B attempts purchase. | **PASS** — **400** `reserved by another buyer`. |

---

## 3. Vulnerabilities and fixes applied (this session)

| Issue | Risk | Mitigation shipped |
|-------|------|---------------------|
| Offer accepted after ticket sold / insufficient inventory | Seller could accept negotiation on unavailable inventory. | `OfferViewSet.accept` runs in **`transaction.atomic()`** with **`select_for_update`** on offer + ticket; validates ticket **not sold/rejected/payout**, **quantity**, and **blocks accept** if another buyer holds a **non-expired** reservation. |
| Pending offers survive competing purchase | Stale UI/API state; seller confusion. | **`_reject_pending_offers_for_ticket_ids()`** on successful **`create_order`** and **`guest_checkout`** (before order persist). |
| Expired reservation still “exclusive” to wrong buyer | Stale checkout could block or allow wrong users. | **`_sync_expired_cart_reservation()`** + **`release_abandoned_carts()`** at start of order transactions; **`create_order`** rejects purchase if another user holds non-expired **reserved** row; guest path matches **`reservation_email`**. |
| Admin could not reject fraudulent **active** listings | Moderation gap after approval. | **`admin_reject_ticket`** allows **`pending_verification`**, **`active`**, and **`reserved`**; clears reservation fields; **rejects pending + accepted** `Offer` rows on that ticket. |

---

## 4. Technical recommendations before going live

1. **Database:** Run the full suite on **PostgreSQL** (staging) with concurrent load tests; SQLite serializes writes and may hide real DB-level race conditions.
2. **Reservation TTL:** Expose **`RESERVATION_TIMEOUT_MINUTES`** in admin/settings and align marketing copy (e.g. “10 minutes” vs “15 minutes”).
3. **Notifications:** Emit explicit events when offers are **auto-rejected** (sale to another buyer, admin rejection) — email or in-app, to reduce support tickets.
4. **Audit log:** Persist admin reject/approve actions with actor, timestamp, and ticket id for compliance.
5. **Rate limits:** Keep/verify **`ScopedRateThrottle`** on offers and checkout; add abuse monitoring on `reserve` + `create_order`.
6. **Idempotency:** Payment gateways should use **idempotency keys** on `create_order` to avoid duplicate charges on retries.
7. **Monitoring:** Alert on spikes of **400** responses on `orders`, `offers`, and `reserve` endpoints.
8. **E2E in CI:** Run `launch_edge_case_qa` + `test_premium_offer_e2e` on every deploy to `main`.

---

## 5. How to re-run

```bash
cd backend
python manage.py test launch_edge_case_qa -v 2
```

---

*This document is generated as part of the SafeTicket pre-launch QA mandate. For questions, see `backend/launch_edge_case_qa.py` and `backend/users/views.py` (helpers: `_reject_pending_offers_for_ticket_ids`, `_sync_expired_cart_reservation`, `release_abandoned_carts`).*
