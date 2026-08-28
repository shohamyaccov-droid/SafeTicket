# Mobile UI polish summary — TradeTix

Date: 28 August 2026  
Source: 68s iPhone screen recording (`WhatsApp Video 2026-08-28 at 14.39.07.mp4`, 384×848) plus local verification at **390×844** and **iPhone SE 375×667**.

93% of traffic is mobile (primarily iOS). This pass treated the recording as the source of truth for friction, then applied native-app spacing, tap, and overlay rules.

---

## What the recording showed

| Moment | Friction |
| --- | --- |
| Homepage hero + last-minute row | Sticky navbar packed **התחבר / שלום + username / TradeTix / ☰ / + מכירה**. Logged-in greeting truncated (`…שלום, hamyaccov`) and collided with the logo. |
| Horizontal event cards | Green WhatsApp FAB + blue **+** FAB stacked on the physical left, covering **לרכישת כרטיסים** / **צפו במועדים** on the peeking left card. Desktop carousel arrows sat on the tiles. |
| Artist dates + event details | Same FAB stack overlayed body copy, then **סינון ומיון**. Raising the FABs above the sticky **קנה עכשיו** bar parked WhatsApp in the middle of the ticket list. |
| Checkout summary | Coupon **הפעל** looked like an unstyled chip; terms checkbox was a small hit area. PayMe itself is third-party (out of scope). |
| iPhone SE risk | Hamburger was already shrinking to **40×40** under 380px. Header would wrap or overlap. |

---

## Fixes shipped

### 1. Floating buttons no longer cover purchase UI

- **Removed the duplicate mobile `+` FAB** on all phone widths. Sell stays in the navbar (`+ מכירה` / icon-only on SE). The extra 56px disc was the main object covering card CTAs.
- **WhatsApp** is a 48×48 disc, `z-index: 880` (under the 900 buy bar). It **hides while scrolling down** and returns on scroll-up or after 1.4s idle. It is hidden while any dialog/drawer uses the body-scroll lock (`html.tt-scroll-lock`).
- **Event details with a sticky buy bar:** WhatsApp is `display: none`. Filter, ticket rows, and **קנה עכשיו** stay fully tappable. Support remains in the footer / contact.
- Main content bottom padding dropped from ~10rem (two stacked FABs) to ~5.5rem.

Verified via DevTools: on `/event/eyal-golan-2026-09-15`, `floating-whatsapp` and `mobile-sell-fab` are `display: none`; `scrollWidth === clientWidth`.

### 2. Navbar crowding

- Logged-in **שלום, …** greeting is **hidden in the bar** (still in the drawer).
- Hamburger stays **44×44** even on SE (no more 40px exception).
- Login and sell CTAs are **min 44px**, with `:active` scale/opacity.
- **≤380px:** sell collapses to a 44×44 **+** (aria-label still “מכירת כרטיסים”).
- Logo `clamp` + narrower center slot so it does not sit under the clusters.

Measured at 375×667: login 52×44, logo centered with **no overlap**, hamburger 44×44, sell 44×44, `scrollWidth === 375`.

### 3. Typography & hierarchy

- Section titles (including **כרטיסים של הדקה ה-90** when that row is present) are **1.12rem / 700** on mobile instead of the desktop 1.35rem + global `h2`.
- Hero title slightly tighter (`1.32rem`, negative tracking).
- Global mobile `h2` / `h3` scaled down so other pages match.

### 4. Layout shifts & overflow

- Homepage carousel **arrows and edge fades are hidden on touch**; swipe is the interaction. Horizontal padding is `1rem` instead of `2.75rem` reserved for arrows.
- Card `:hover` lift is disabled on coarse pointers so iOS does not leave a stuck “hover” offset; `:active` uses a 0.98 scale.
- `html`/`body` already clip `overflow-x`; homepage and event pages measured **no horizontal scroll** at 375 and 390.

### 5. Touch targets & tap feedback

- 44px minimum on: navbar controls, back links, artist **התראת כרטיסים**, date-modal rows, notify buttons, footer links, checkout **הפעל**, legal-acceptance row.
- Shared `:active` opacity on buttons (`index.css`, coarse pointer).
- Checkout coupon row finally has CSS (it had markup only): 44px input + **הפעל**.
- Legal checkbox enlarged; label `min-height: 44px`.

---

## Files touched

| Area | Files |
| --- | --- |
| FABs | `FloatingWhatsApp.jsx/.css`, `EventMobileBuyBar.css`, `Navbar.css` |
| Header | `Navbar.css` |
| Home | `Home.css` |
| Global tap | `index.css` |
| Checkout | `CheckoutModal.css` |
| Event / artist / tickets / footer | `EventDetailsPage.css`, `ArtistEventsPage.css`, `TicketSelectionPage.css`, `Footer.css` |

---

## Verification

- Recording frame extract (68s @ ~60fps) for issue list.
- Local Vite `localhost:3000` at **390×844** and **375×667**:
  - Homepage: 44px controls, no wrap, no `+` FAB, WhatsApp in the corner, titles 17.92px, no horizontal overflow.
  - Event details: buy bar present, both FABs hidden, **סינון ומיון** unobstructed.

PayMe (`live.payme.io`) was in the recording; it is an external checkout and was not restyled.

---

## Further recommendations

1. **Logged-in chrome:** a 32px avatar in the left cluster would replace the removed greeting without crowding the logo.
2. **Last-minute row:** keep the orange accent on that section only (today `first-of-type` also paints **מומלצים** orange when last-minute is empty).
3. **WhatsApp on home:** if hide-on-scroll feels jumpy, prefer a 40px collapsed chip that expands on tap.
4. **A more native shell:** consider a small bottom tab bar (בית / חיפוש / מכירה) and retire the hamburger for the top three actions — only if conversion data supports it.
5. **Checkout:** move **הפעל** to a filled primary style once coupon use is material; keep 44px either way.
6. **Real-device pass:** one Safari session on an SE and a Dynamic Island phone after deploy, with a logged-in account, to confirm the drawer greeting and sticky Safari chrome.
