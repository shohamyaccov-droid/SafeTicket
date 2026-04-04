# SafeTicket / TradeTix — Israel Market Launch QA Plan

**Scope:** Mass launch for Israeli users buying tickets for **international concerts** and **football**, with ILS settlement expectations, cross-border inventory, and mobile-first trust.

**Duration target:** Full regression + stress scenarios before go-live.

---

## 1. Auth & onboarding (high priority)

| ID | Scenario | Pass criteria |
|----|----------|---------------|
| A1 | Registration (current product: **instant JWT**, OTP dormant) | `201`, `access` + `refresh`, `is_email_verified: true`, user can call authenticated APIs immediately |
| A2 | Login valid credentials | `200`, tokens + `user` payload |
| A3 | Login wrong password | `401`, no token leak |
| A4 | OTP verify endpoint (`/api/users/verify-email/`) | With cache-seeded OTP: `200` + tokens; invalid OTP: `400` |
| A5 | Cross-origin / Bearer | SPA can auth with `Authorization: Bearer` without CSRF on login |

**Note:** Strict “block login until email verified” is **not** active while OTP sending is dormant. Re-enable OTP + `CustomTokenObtainPair` email check when product requires it.

---

## 2. Transactional & currency integrity

| ID | Scenario | Pass criteria |
|----|----------|---------------|
| C1 | IL event listing (`country=IL`) | ILS quantization (whole shekels); receipt rules where applicable |
| C2 | US/GB/EU listing | USD/GBP/EUR; `quantize_money_decimal` uses **0.01** |
| C3 | Checkout total vs list price | `expected_buy_now_total(unit, qty)` matches `/payments/simulate/` + order creation (**no `ceil(float * 1.1)`** — floating error risk) |
| C4 | Negotiated offer | Fee on offer base; `payment_amounts_match` within tolerance |
| C5 | Cross-currency **rejected** at API | Offers inherit listing currency; no mixed-currency negotiation |
| C6 | **15% platform economics** | `buyer_service_fee` = 10% of bundle; `seller_service_fee` = 5% of bundle; `net_seller_revenue` = base − seller fee; admin **`/api/users/admin/dashboard/stats/`** sums both fees per currency and exposes **`totals_ils`** (FX via `FX_RATES_TO_ILS` / env `FX_USD_ILS`, etc.) |

---

## 3. Timezone handling

| ID | Scenario | Pass criteria |
|----|----------|---------------|
| T1 | Event stored in UTC | `Event.date` is timezone-aware in DB |
| T2 | API JSON | ISO-8601 with offset (or Z); clients can parse |
| T3 | UX copy | Product/copy clarifies “event local time” vs “your time” where relevant |
| T4 | Escrow / payout dates | `payout_eligible_date` uses event end + policy; no off-by-one day vs Israel |

**Risk:** If UI shows only server-local strings, travelers may misread London vs Tel Aviv; verify frontend formatting (`Intl`, `timezone` labels).

---

## 4. Listing flow (hybrid seating)

| ID | Scenario | Pass criteria |
|----|----------|---------------|
| L1 | Event with `venue_place` + sections | `GET /events/:id/` includes `venue_detail.sections`; `POST /tickets/` accepts `venue_section` |
| L2 | Event without structured venue | `custom_section_text` or legacy `section`; no `500` |
| L3 | IL listing | Receipt + legal declaration when required |
| L4 | Multipart PDF / quantity | Matches `pdf_files_count` / auto-split rules |

---

## 5. Notification reliability

| ID | Scenario | Pass criteria |
|----|----------|---------------|
| N1 | Offer created | API returns **201** immediately; SMTP runs in **background thread** |
| N2 | SMTP failure | Logged (`logger.error` / exception hook); **no 500** to client |
| N3 | `EMAIL_TIMEOUT` | SMTP connect/send capped (e.g. 5s default in settings) |

**Manual:** No UI spinner > ~1s attributable to “waiting for email” on offer submit.

---

## 6. Edge cases & abuse

| ID | Scenario | Pass criteria |
|----|----------|---------------|
| E1 | Double-click “Submit offer” | Idempotent or second request rejected cleanly (no duplicate accepted offers / no 500) |
| E2 | Offer amount ≤ 0 or negative | `400` validation |
| E3 | Rapid negotiate / checkout | Locks + `select_for_update` prevent oversell |
| E4 | Guest vs registered offer/payment | Email match rules enforced |

---

## Automation map

- Django: `users.tests.*`, `users.tests.test_fifteen_percent_fees`, `test_e2e_email_otp`, `test_*currency*`, `test_*negotiation*`, `test_hybrid_seating_listing_email_resilience`
- Do **not** rely on `manage.py test` with empty labels if discovery conflicts; pass explicit modules (see `QA_STATUS_REPORT.md`)

---

## Sign-off checklist (go / no-go)

- [ ] All **P0** automated tests green on staging DB
- [ ] Render build: `migrate` applied (`0041`+ seller fee + dashboard ILS rollups)
- [ ] Resend/domain: verified sender; `EMAIL_TIMEOUT` + threaded send deployed
- [ ] Smoke: register → browse event → offer → (mock) pay on staging
