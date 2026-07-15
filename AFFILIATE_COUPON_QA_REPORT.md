# Affiliate Coupon System — Implementation & QA Report

**Date:** 2026-07-15  
**Scope:** Buyer fee 15%, affiliate coupon one-time use (5% buyer / 5% affiliate / 5% platform), checkout integration, automated tests

---

## Business logic implemented

| Mode | Buyer pays | Platform keeps | Affiliate |
|------|------------|----------------|-----------|
| No coupon | base + **15%** | 15% of base | 0 |
| Valid coupon | base + **10%** | **5%** of base | **5%** of base |

Buyer discount = 5% of listing base (fee drops from 15% → 10%).

---

## Schema (industry pattern)

Inspired by coupon-service LLD / ecommerce unique-redemption designs:

1. **`AffiliatePartner`** — partner identity + default commission  
2. **`Coupon`** — unique `code`, windows, rates, global `redemption_count`  
3. **`CouponRedemption`** — ledger with **partial UNIQUE** on `(coupon, buyer_key)` where `status ∈ {pending, redeemed}`  
4. **`Order`** fields: `coupon`, `coupon_code_snapshot`, `buyer_fee_discount`, `affiliate_commission`, `platform_net_fee`

Concurrency: `transaction.atomic` + `select_for_update` on coupon + DB unique constraint + `IntegrityError` → `already_used`. Abandoned/cancelled checkouts **release** pending redemptions so the slot can be reused.

---

## API / UI

- `POST /api/users/coupons/validate/` — preview only (no claim)  
- `coupon_code` on `POST /api/users/orders/` and guest checkout  
- CheckoutModal: apply/clear coupon UI (info + payment steps)  
- Admin: AffiliatePartner / Coupon / CouponRedemption  
- Render start: `python manage.py seed_affiliate_coupon` → demo code **`AFFILIATE5`**

---

## Tests created

### Django (`users.tests.test_affiliate_coupons`)
- Base fee = 15% on ₪100 → ₪115  
- Affiliate split exact 5/5/5 → buyer total ₪110  
- Invalid code → 400 `invalid_code`  
- Validate OK then second validate after claim → `already_used`  
- Create order with coupon stores split fields + pending redemption  
- Wrong client total with coupon rejected  
- Second claim same buyer fails (double-use)

### Frontend (Vitest)
- `src/utils/priceFormat.coupon.test.js` — 15% and coupon math (3 tests)

### Regression suite run (PASS)
`test_fifteen_percent_fees`, `test_guest_checkout_flow`, `test_concurrency_guards`, `test_deploy_smoke_pass`, `test_payment_scary_cases`, `test_launch_offer_validation`, `test_affiliate_coupons` — **21+7 OK**

---

## Bugs found during QA loop & fixes

| Bug | Fix |
|-----|-----|
| SQLite `database is locked` on threaded race test | Replaced with deterministic sequential double-claim test (UniqueConstraint still covered) |
| Vitest wrong import paths | Fixed relative imports under `src/utils/` |
| Coupon claim after order save could commit then fail | `transaction.set_rollback(True)` on coupon claim failure |
| Circular import risk in `coupon_views` | Local CSRF passthrough decorator |

---

## Default fee change note

`PLATFORM_BUYER_SERVICE_FEE_RATE` default **0.05 → 0.15**. Frontend `BUYER_SERVICE_FEE_PERCENT` **5 → 15**. Override via env if needed.

---

## How to try on staging

1. Deploy (migrate `0066` + start_render seeds `AFFILIATE5`)  
2. Checkout any listing → enter **`AFFILIATE5`** → Apply  
3. Confirm total = base × 1.10  
4. Complete purchase once → second attempt with same user/email must fail
