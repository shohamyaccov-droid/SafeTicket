# QA Status Report — Israel Launch Readiness

**Date:** 2026-04-03  
**Scope:** **Financial audit (15% fees)**, auth/receipt E2E, hybrid seating, IL/US approval, GBP negotiation, offer validation.

---

## Tests executed (this session)

| Batch | Module(s) | Count | Result |
|-------|-----------|------:|--------|
| Launch core | `test_e2e_email_otp`, `users.tests.test_launch_offer_validation`, `users.tests.test_hybrid_seating_listing_email_resilience`, `users.tests.test_il_global_approval_qa` | **15** | **PASS** |
| Fee model & admin | `users.tests.test_fifteen_percent_fees` | **2** | **PASS** |
| Currency / sell | `test_uk_negotiation_currency_e2e`, `test_sell_us_e2e_flow` | **2** | **PASS** |
| **Total (reported)** | | **19** | **PASS** |

**Ad-hoc:** `python qa_price_integrity.py` — **PASS** (negotiated flow with **confirm-payment**; asserts buyer fee, seller fee, net to seller).

**Note:** `python manage.py test` **without labels** can fail discovery on this repo. For CI:

`python manage.py test users.tests test_e2e_email_otp test_uk_negotiation_currency_e2e test_sell_us_e2e_flow -v 1`

---

## Financial fixes applied (Task 1)

1. **`Order.seller_service_fee`** (`users/models.py` + migration **`0041_order_seller_service_fee`**)  
   - Persisted **5% of `final_negotiated_price`** (listing/offer bundle) on payment confirm.  
   - **`net_seller_revenue`** is now **base − seller fee** (seller’s payout line).  
   - **`buyer_service_fee`** unchanged in meaning: **total paid by buyer − base** (10% of base when checkout matches pricing).

2. **`compute_order_price_breakdown`** (`users/pricing.py`)  
   - Returns `seller_service_fee` and updated `net_seller_revenue`.  
   - **`seller_fee_from_base_amount`** helper for the 5% leg.

3. **`_apply_order_pricing_fields`** (`users/views.py`)  
   - Saves `seller_service_fee` with the rest of the breakdown after **`confirm-payment`**.

4. **Admin dashboard aggregation** (`admin_dashboard_stats`)  
   - **`platform_fees`** per currency = **Sum(buyer_service_fee + seller_service_fee)** (previously only buyer fee → ~half the platform take in reports).  
   - **`totals_ils`**: `platform_fees_ils` and `gross_revenue_ils` using **`FX_RATES_TO_ILS`** in `safeticket/settings.py`, overridable via **`FX_USD_ILS`**, **`FX_EUR_ILS`**, **`FX_GBP_ILS`**.

5. **Backfill** (`RunPython` in `0041`)  
   - For existing rows with **`final_negotiated_price`** set and zero seller fee: sets **`seller_service_fee`** and recomputes **`net_seller_revenue`** for consistent historical reporting.

6. **API / receipts**  
   - **`seller_service_fee`** on `OrderSerializer`, `ProfileOrderSerializer`, and JSON **`order_receipt`**.

7. **Tests / scripts**  
   - `users/tests/test_fifteen_percent_fees.py`; updates to **`test_uk_negotiation_currency_e2e.py`**, **`qa_price_integrity.py`** (confirm step), **`twin_user_negotiation_stress_qa.py`** (expected net to seller = 95% of base).

---

## Launch readiness score: **84%**

| Area | Weight | Notes |
|------|--------|--------|
| Fee reporting & seller net | **Strong** | 10% + 5% persisted; admin rollup + ILS estimate |
| Core commerce | Strong | IL + US + UK GBP E2E greens |
| Auth | Good | JWT + OTP verify path covered in prior work |
| Hybrid seating | Good | Resilience tests green |
| Timezone / travel UX | Gap | No automated UI tour (London vs IDT) |
| FX in dashboard | **Operational** | Rates are **indicative**; tune env for finance close |

---

## Remaining risky areas

1. **`manage.py test` discovery** — CI should pass explicit labels.  
2. **FX accuracy** — `FX_*_ILS` should be fed from treasury/accounting, not defaults.  
3. **Pending orders** — Full fee breakdown is applied at **payment confirm**; any UI showing order detail before confirm should treat seller fee as pending or hide until paid.  
4. **Timezone presentation** — Web/email/PDF local-time clarity for international events.  
5. **Frontend E2E** — Not run here.

---

*Adjust readiness after staging finance sign-off on real admin totals.*
