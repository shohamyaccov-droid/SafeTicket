# Mobile / iPhone QA summary — TradeTix

Date: 28 August 2026  
Scope: Buyer and seller flows in the React SPA (`frontend/src`), with an iPhone-class viewport (390×844) against the local Vite + Django stack.

This pass targeted three failure classes:

1. Modal scroll / exit lock (especially the Buy / checkout dialog)
2. iOS Safari viewport and touch quirks (`100vh`, body rubber-banding, horizontal overflow)
3. Layout jumps when data or dialog state changes

---

## What was tested

### Buyer path

| Surface | How it was exercised |
| --- | --- |
| Homepage | Loaded at 390×844. Opened **התחבר** (login modal), measured overlay vs sticky navbar, closed via **סגירה**. No page-level horizontal scroll. |
| Event details | `/event/eyal-golan-2026-09-15` (live listing). Used **קנה עכשיו** on the sticky buy bar. |
| Checkout (“Buy”) modal | Confirmed overlay `z-index` 13050 vs navbar 12000, body scroll lock (`html.tt-scroll-lock` + `position: fixed`), inner `overflow-y: auto`, 44×44 close control, then dismissed. |
| Login / register overlay | Same lock + close-button checks as homepage. |
| Waitlist / make-offer / date picker | Code-path + CSS review (waitlist and make-offer share the new overlay stack; date picker locks body when open). |

### Seller path

| Surface | How it was exercised |
| --- | --- |
| Sell wizard `/sell/new` | Loaded at 390×844. Event / artist selects, “בקשה להוספת אירוע”, sticky continue CTA. `scrollWidth === clientWidth` (no horizontal overflow). Body not locked on the page itself. |
| Become-seller / sell-completion / negotiation | Code-path + CSS: same scroll-lock hook and overlay `z-index` as checkout. |

### Automated checks

- `useBodyScrollLock` unit tests (lock, nested modals, `locked=false`)
- `LoginQuickModal` tests
- Production `vite build` after the CSS/JS changes

---

## Bugs found

### P0 — Buy modal sat *under* the sticky navbar (could not scroll or exit)

The navbar is `position: sticky; z-index: 12000`. Checkout, waitlist, become-seller, negotiation, email-alert, home date picker, and sell-completion overlays were **1000–10050**. On iPhone the hamburger bar painted on top of the dialog, so taps on **×** hit the navbar instead of close, and the sheet could not be scrolled as a dedicated layer.

This matches the reported “Buy modal locked the screen”.

### P0 — iOS body scroll was not locked for dialogs

Only the nav drawer set `document.body.style.overflow = 'hidden'`. iOS Safari ignores that without `position: fixed` + scroll restoration. Background rubber-banding stole touch events from the dialog.

### P1 — Checkout sheet taller than the visual viewport

`.modal-overlay.checkout-modal-overlay` kept 12px + safe-area padding on mobile while `.modal-content` used `max-height: 100dvh`. Combined with `min-height: 540px / 620px` on the checkout shells, the sheet overflowed the overlay. The overlay did not scroll (`overflow` default), so content and actions could be clipped.

The universal `.modal-content * { max-width: 100% }` rule also interfered with inner overflow.

Close was `position: absolute`, so it scrolled away instead of staying tappable.

### P1 — Horizontal overflow and toast on small screens

`html`/`body` did not clip `overflow-x`. Toasts used `z-index: 10000` (under navbar, same as old checkout) and a 32px close control.

### P2 — Remaining `100vh` without `dvh`

Admin offers page and admin review `max-height` used `100vh` only (iOS URL bar gap).

### P2 — CLS

Homepage carousels and event ticket lists had little reserved height, so rows jumped when listings arrived.

---

## Code changed

### Shared iOS scroll lock

- Added `frontend/src/hooks/useBodyScrollLock.js` (refcount, `position: fixed`, restore `scrollY`, `html.tt-scroll-lock`).
- Wired into: `CheckoutModal`, `LoginQuickModal`, `WaitlistSignupModal`, `BecomeSellerModal`, `ShabbatModal`, `NegotiationModal`, `EmailAlertModal`, `AdminReviewModal`, Home date picker, Event Details make-offer, Navbar drawer (replaced the old overflow-only lock).

### Overlay stacking (above navbar 12000)

| Layer | z-index |
| --- | --- |
| Navbar / drawer | 12000–12002 (unchanged) |
| Checkout, make-offer, waitlist, become-seller, negotiation, email-alert, home date, sell-completion | **13050** |
| Login quick modal | **13100** |
| Shabbat (on top of checkout) | **13200** |
| Admin review | 14000 |
| Toasts | **16000** |

### Checkout / Buy sheet CSS (`CheckoutModal.css`)

- Overlay `overflow: hidden`, `overscroll-behavior: contain`.
- Mobile: overlay padding **0**, shell `min-height: 0`, `max-height: 100dvh`.
- Desktop-only min-heights 540/620 so iPhone no longer forces a 620px sheet.
- Close control is **sticky**, 44×44, in document flow (does not scroll off).
- Removed the `* { max-width: 100% }` sledgehammer.

### Other CSS

- `index.css`: `overflow-x: clip` on `html`/`body`/`#root`; `touch-action: manipulation` on buttons; `html.tt-scroll-lock` overflow hidden.
- Login, waitlist, become-seller: bottom sheets on ≤480px, 44px close, `100dvh` max-height.
- Home date modal: `max-height: 90dvh`, overlay 13050, close min-height 44.
- Toast: safe-area top, 44px close on mobile.
- Event details ticket grid and home carousel: min-heights to reduce CLS.
- Admin offers / admin review: `dvh` fallbacks.

---

## Browser verification (this pass)

iPhone 14-class viewport (390×844):

- Login overlay z-index **13100** > navbar **12000**; body `position: fixed`; close **44px** tall; close visible; no horizontal scroll; dismissed with **סגירה**.
- Checkout overlay z-index **13050**; body locked; content `overflow-y: auto` and `scrollHeight > clientHeight` (sheet scrolls); close **44×44**; `min-height: 0`; dismissed.
- Sell `/sell/new`: `scrollWidth === 390`; body not locked on the form page.

---

## Further UI recommendations (not done here)

1. **Single modal primitive** — A `<Modal>` with portal, lock, focus trap, and Escape would prevent z-index drift the next time a dialog is added.
2. **Focus trap** — Tab can still leave the checkout sheet into the page behind it.
3. **Checkout close vs cart hold** — The first close tap can race the “שומר כרטיס…” reservation. Consider always dismissing the UI immediately and releasing the hold in the background.
4. **Login close `float: left`** — Works, but a flex header row would be cleaner than sticky + float.
5. **Venue maps** — `touch-action: none` on some stadium maps is correct for pinch-zoom; keep listing list as the primary vertical scroll on mobile so the map does not capture the whole page.
6. **Real-device Safari** — This pass used Chromium device metrics. Confirm on a physical iPhone (visualViewport + keyboard shrinking `dvh`).
7. **Sticky sell CTA** — Step 1 uses an in-flow “המשך למחיר ומושבים”; later steps use `.sell-submit-sticky-wrap`. Spot-check step 2 with the keyboard open.

---

## Files touched

`frontend/src/hooks/useBodyScrollLock.js`, `useBodyScrollLock.test.js`, `index.css`, `CheckoutModal.{jsx,css}`, `LoginQuickModal.{jsx,css}`, `WaitlistSignupModal.{jsx,css}`, `BecomeSellerModal.{jsx,css}`, `ShabbatModal.{jsx,css}`, `NegotiationModal.{jsx,css}`, `EmailAlertModal.{jsx,css}`, `AdminReviewModal.{jsx,css}`, `Navbar.jsx`, `Toast.css`, `SellCompletionModal.css`, `Home.{jsx,css}`, `EventDetailsPage.{jsx,css}`, `AdminOffersPage.css`, this document.
