# TradeTix — Mobile UX & E2E QA Report

**Date:** 2026-04-04  
**Scope:** Event Details sticky map (mobile), Personal Area (Dashboard / Profile) mobile pass, listing-to-sale financial flow validation (automated).

---

## 1. Mobile UX Changes — Sticky Seating Map

### Implementation (Event Details — `event/:eventId`)

- **Structure:** The **סינון ומיון** bar was moved **inside** `tickets-section` (still directly under the hero visually) so the filter strip and the seating map share one scroll context with the ticket list.
- **Sticky filter bar:** On viewports **`max-width: 768px`**, `.event-details-filters-sort-bar` uses `position: sticky` with `top: env(safe-area-inset-top)` and high `z-index`, solid card background, and shadow so **Filter / Sort stay reachable** while scrolling.
- **Sticky map:** `.venue-map-sticky-container` is `position: sticky` with `top: calc(env(safe-area-inset-top) + 4.25rem)` so the map pins **under the collapsed filter row** (~68px). When the filter panel is open, `:has(.mobile-open)` increases the offset so the map clears the expanded panel (requires **`:has()`** — Safari 15.4+, Chromium 105+).
- **Map height:** Map content uses **`clamp(28vh, 35vh, 40vh)`** with a **40vh** cap, matching the 30–40% viewport requirement. Interactive Menora / `VenueMapPin` wrappers fill the box without forcing a tall min-height on small screens.
- **Ticket list:** List remains in normal document flow with **extra bottom padding** (`safe-area-inset-bottom`) so the last rows are not hidden behind the home indicator. Scrolling is **page-level** (no nested scroll trap), which works well with `position: sticky` for the map.
- **Desktop:** Unchanged — split layout from **`min-width: 992px`** still uses side-by-side map + list with the existing sticky map offset.

### Files touched

- `frontend/src/pages/EventDetailsPage.jsx` — filters block relocated into `tickets-section`; `type="button"` on filter actions.
- `frontend/src/pages/EventDetailsPage.css` — mobile sticky rules, map height clamps, `:has()` offset for open filters.

---

## 2. Personal Area (Dashboard / Profile) — Mobile Audit

### Dashboard (`Dashboard.css`, `max-width: 768px`)

- Safe-area **bottom padding** on `.dashboard-container`.
- Slightly smaller **header title** for small screens.
- **Compact rows:** `min-height: 52px`, wrap-friendly `gap`, vertical padding for list rows.
- **Tap targets:** `.row-action-button` **minimum 44×44px** (Apple HIG–aligned).
- **Pending verification** callout: `flex-wrap`, spacing, SVG not crushed by long Hebrew lines.
- **Section titles** scaled down for readability.

### Profile (`Profile.css`, `max-width: 768px`)

- Tighter horizontal padding + **safe-area bottom**.
- **Tab buttons:** `min-height: 48px`, wrap with gap.
- **Cards:** fuller padding; **primary actions** full-width with `min-height: 48px`.

### Verification status

- Dashboard **status badges** and **pending verification** blocks use wrap-friendly flex; no new overlaps introduced by these rules. Manual check recommended on **iPhone SE width (320px)** for longest translated strings.

---

## 3. E2E Simulation — Success Rate (Listing → Offer → Counter → Pay)

| Step | Automated coverage | Result |
|------|-------------------|--------|
| Seller lists **international** ticket (no IL receipt) | `test_international_launch_e2e.InternationalLaunchE2ETest.test_us_listing_without_receipt_and_buyer_offer` | **PASS** |
| Buyer offer + **double-submit idempotency** (one offer) | `test_duplicate_initial_offer_within_five_seconds_rejected` | **PASS** |
| Full **GBP** negotiation → accept → checkout → confirm | `test_uk_negotiation_currency_e2e` | **PASS** |
| Confirm-payment fast path (receipt async) | `InternationalLaunchReceiptAsyncE2E` | **PASS** |

**Declared success rate for this automated listing-to-sale path:** **1 / 1** (all scenarios above green in the last run).

*Note:* “User B navigates sticky map on mobile” is a **manual / device lab** check; the implementation is in place as described in §1.

---

## 4. Financial Validation — 15% Platform Model

**Rule (locked in `users.pricing.compute_order_price_breakdown`):**

- Buyer pays **negotiated base + 10%** buyer service fee.
- Seller is charged **5%** seller service fee on the negotiated base.
- **Platform total = 10% + 5% = 15%** of the negotiated base (split across buyer and seller).

**Evidence (automated):**

- `users.tests.test_fifteen_percent_fees` — ILS example: base 100 → buyer pays 110, seller fee 5, **net seller 95**; admin stats aggregate seller fees.
- UK E2E: base **480 GBP** → buyer **528** (480 + 48), **seller fee 24** (5% of 480), **net seller 456**, **platform fees 72** (48 + 24) = **15% of 480**.

**Currency note:** Amounts are computed per order currency (ISO 4217); quantization uses existing money helpers — same **percent rules** apply across GBP / USD / ILS in tests.

---

## 5. Device Compatibility (Simulated)

| Target | Simulation method | Notes |
|--------|-------------------|--------|
| **iPhone** | Chrome/Edge DevTools — iPhone 14 Pro (~393×852), safe-area env | Sticky map + filter bar respect `safe-area-inset-*`; map height ~35vh. `:has()` supported on iOS 15.4+. |
| **Android** | DevTools — Pixel 7 (~412×915) | Same CSS; Material-style nav usually no notch — `env(safe-area-inset-top)` often 0. |
| **Small width** | 360px width | Filter toggle remains full-width; ticket rows rely on existing compact layout + new tap targets. |

**Recommendation:** One **on-device** pass on iOS Safari and Chrome Android to confirm touch scrolling with the interactive map and the expanded filter panel.

---

## 6. Commands Run (QA engineer log)

```bash
cd backend
python manage.py test users.tests.test_fifteen_percent_fees test_international_launch_e2e test_uk_negotiation_currency_e2e -v 1
```

**Result:** `OK` (6 tests).

---

## 7. Follow-ups (optional)

- **Sticky offset tuning:** If the filter bar height changes (new controls), adjust `4.25rem` / `:has()` `min(42vh, 11rem)` in `EventDetailsPage.css`.
- **`position: relative` navbar on mobile:** Navbar scrolls away with content; sticky map/filter anchor to the **viewport top**, which is correct once the user has scrolled past the hero.
- **Visual regression:** Consider Playwright screenshots for `event/:eventId` at 390px width.
