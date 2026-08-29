# Overnight mobile CRO audit — TradeTix

**Date:** 30 August 2026  
**Branch:** `main`  
**Scope:** Seller `/sell/new` and buyer checkout (event sticky **קנה עכשיו** → checkout modal → PayMe), iPhone / iOS first.  
**Goal:** Reduce mobile friction on ticket uploads and purchases, close GA4 funnel gaps, and ship three trust/urgency lifts.

Assumed weekend e-commerce pattern (no new GA export in this pass): homepage and event views hold, **add_to_cart → begin_checkout** drops on mobile (keyboard + CTA occlusion), **begin_checkout → purchase** drops on identity/trust, and seller drop-off is highest between event pick and first file attach.

---

## Part 1 — Mobile UX findings and fixes

### Already in good shape

| Surface | Finding |
|---|---|
| Event sticky buy bar | `EventMobileBuyBar` is fixed to the bottom, **קנה עכשיו** is ≥44px, shows a spinner while checkout opens, and hides the WhatsApp FAB. |
| Listing row buy | `.viagogo-buy-button` already has `min-height: 44px` and a disabled/spinner state (`מעביר לתשלום…`). |
| Checkout pay / continue | Primary actions are 48px, disabled while loading, and show phase-specific spinners. Double-submit is guarded in JS (`paymentSubmittingRef`). |
| Sell publish | Sticky **הצע כרטיס למכירה** is 48px with spinner + `listingSubmitLockRef`. First field error already scrolls into view. |
| Checkout inputs | Guest / card fields already use `min-height: 44px` on small viewports. CSS already had `scroll-padding-bottom` but **no JS** to fight the iOS keyboard. |

### Friction that was fixed

1. **iOS keyboard covering fields**  
   Added `useFocusScrollIntoView` on `/sell/new` and checkout. After `focusin` on text/tel/email inputs, the field scrolls to center; if `visualViewport` still covers it, the modal/page scrolls further.  
   Added `useVisualViewportInset` in checkout: writes `--vv-keyboard-inset` so the sticky pay row sits above the software keyboard.

2. **Sticky seller CTA vs WhatsApp FAB**  
   Sell sticky bar `z-index` raised to **900** (same stack as the event buy bar). `body.has-sell-mobile-cta` hides `.floating-whatsapp` / `.mobile-sell-fab` so the publish button stays tappable.

3. **Phone-capture tap targets**  
   `BuyerIdentityInlineForm` inputs and actions are now **44×44** minimum, with a spinner on save (prevents double-submit on slow profile PATCH).

4. **Seating toggle on sell**  
   Optional seating expander now has `min-height: 44px`.

### Buy Now placement

On mobile event pages, **קנה עכשיו** is already a sticky bottom bar (not only in the ticket row). This pass kept that pattern and made the bar more conversion-useful (scarcity line — see Part 3). Checkout continue/pay remains a sticky footer inside the sheet, now offset for the keyboard.

---

## Part 2 — Analytics / bottleneck tracking

### Funnel events (GA4)

| Event | Status before | Status after | Where it fires |
|---|---|---|---|
| `view_item` | Present (`Analytics.ticketViewed`) | Unchanged | Event details load |
| `add_to_cart` | Present (`Analytics.addToCart`) | Unchanged | Event **קנה עכשיו** / `beginBuy` |
| `begin_checkout` | Present (`Analytics.checkoutStart`) | Unchanged | Deduped 2s click lock + 10 min session TTL per ticket. **Must not** fire on empty modal mount. |
| `purchase` | Present (`Analytics.checkoutComplete`) | Unchanged | Checkout success + PayMe return (`PaymeCheckoutSuccess`) |
| `begin_ticket_upload` | **Missing** | **Added** | First successful ticket file attach on `/sell/new` (single / multi / package). Once per session. **Does not** emit Meta Lead. |

Seller Lead remains `ticketListed` → `generate_lead` only after HTTP 2xx with a created listing id.

### How to read weekend drop-off in GA4

Recommended exploration (last 7 days, device category = mobile):

1. `view_item` → `add_to_cart` — listing-grid / price-trust problem.  
2. `add_to_cart` → `begin_checkout` — should be near 1:1 (same tap). If not, checkout modal failed to open.  
3. `begin_checkout` → `purchase` — identity, keyboard, PayMe redirect, or trust.  
4. `begin_ticket_upload` → `generate_lead` — file attached but listing not published (auth, validation, or abandon).

---

## Part 3 — Three CRO improvements shipped

### 1. Visual scarcity on the sticky buy bar

When the cheapest buyable group has **1–3** tickets left, the mobile bar replaces the generic “לכרטיס, לפני דמי שירות” hint with:

- `נשאר כרטיס אחד בקבוצה הזו`
- `נשארו N כרטיסים בקבוצה הזו`

Hidden above 3 so we do not manufacture fake urgency on deep inventory.

### 2. SafePay trust badge (checkout + event list)

New compact `SafePayTrustLine` on checkout **info** and **payment** steps:

> SafePay — הכסף בנאמנות עד 36 שעות אחרי האירוע. כרטיס תקף בזמן — או החזר מלא.

The event-list guarantee banner now uses the same escrow wording instead of a generic “אחריות 100%” line.

### 3. Calmer phone verification (less intrusive)

Checkout identity capture was styled as an orange warning wall (“חסר מספר טלפון…”). That reads like a block, not a step.

- Copy: “אישור הרכישה יישלח ב-SMS. מספר נייד בלבד — בלי לעזוב את הקופה.”
- Visual: blue/green trust panel aligned with `--primary-blue`, 44px fields, spinner on save.
- Seller auth lead: “כדי לפרסם: אימייל, מספר נייד וסיסמה. השם אופציונלי — פרטי תשלום אפשר להוסיף אחר כך.”

---

## Files touched

- `frontend/src/hooks/useFocusScrollIntoView.js` (+ test)
- `frontend/src/hooks/useVisualViewportInset.js`
- `frontend/src/utils/analytics.js` + `analytics.conversions.test.js`
- `frontend/src/pages/Sell.jsx` / `Sell.css` / `Sell.test.jsx`
- `frontend/src/pages/EventDetailsPage.jsx`
- `frontend/src/components/CheckoutModal.jsx` / `CheckoutModal.css`
- `frontend/src/components/EventMobileBuyBar.jsx` / `.css` / `.test.jsx`
- `frontend/src/components/BuyerIdentityInlineForm.jsx` / `.css`
- `frontend/src/components/SellCompletionModal.jsx` / `.test.jsx`
- `frontend/src/components/SafePayTrustLine.jsx` / `.css`

---

## Strategic recommendations (not shipped)

1. **One-tap Apple Pay / Google Pay on the sticky bar** — skip the info sheet for returning buyers with a saved phone. Highest expected lift on `begin_checkout → purchase`.  
2. **Hold timer as a progress ring on the sticky pay button** — the 10-minute reserve is already there; making it visible on the CTA reduces “I’ll come back later” (listings get released).  
3. **Seller: attach file on step 1** — moving PDF upload before seating details would fire `begin_ticket_upload` earlier and let us recover abandoners with a “finish your listing” SMS.  
4. **Scarcity only from live `available_count`** — do not add “X people viewing” without a real signal; it will erode SafePay trust.  
5. **GA4 marketer setup** — register `begin_ticket_upload` as a custom event / key event and build a seller funnel: `page_view(/sell/new)` → `begin_ticket_upload` → `generate_lead`.  
6. **PayMe return reliability** — keep `purchase` on both in-modal success and `/payme/success`; weekend mobile drop-off often is a lost redirect, not a failed charge.

---

## QA

- Unit: analytics conversion guards, EventMobileBuyBar scarcity, focus-scroll hook, SellCompletionModal copy.  
- Frontend production build after the change set.  
- Manual iPhone-class (390×844) check on Vite: `/sell/new` loaded. **המשך למחיר ומושבים** measured **44px** tall. `body.has-sell-mobile-cta` applied; WhatsApp FAB hidden. Wizard correctly blocked step 2 without an artist. Seller auth lead shows the calmer copy.  
- Live event/checkout path could not be clicked in this pass: the local API did not return events (`לא הצלחנו לטעון את האירועים`). Checkout keyboard inset + SafePay + scarcity are covered by unit tests and code review.
