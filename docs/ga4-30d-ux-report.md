# TradeTix GA4 UX report — last 30 days

**Property:** `538996752` (Measurement ID `G-D0P22V9YLH`)  
**Window:** `30daysAgo` → `today` (27 Jul – 26 Aug 2026)  
**Fetched:** 26 Aug 2026, 14:02 UTC via the Google Analytics Data API (Application Default Credentials)  
**App:** React SPA (`frontend/src/App.jsx`) + Django API

This report answers three questions: where users drop, whether they reach events, and which five product changes would move checkout.

---

## How to read the numbers

- **Path counts and conversion events are independent**, not a closed same-session funnel. A closed `runFunnelReport` (Home → Artist → Event → `begin_checkout` → `purchase`) was attempted and rejected: GA4 does not allow `pagePath` inside funnel steps.
- **Checkout is a modal** on the event page. There is no `/checkout` browse path. We count `begin_checkout` and `purchase` events. `/checkout/payme/success` is the PayMe return URL.
- **GA4 has no exit-page metric** (unlike Universal Analytics). “Highest exit pages” is a proxy: landing-page bounce, plus high-bounce `pagePath` rows.
- **Landing-page rows with unique `fbclid` query strings are fragmented.** The top-50 landing report under-counts Instagram. Route-family session counts (`/sell/new` = 903) are the reliable volume numbers.
- **25–26 Aug bounce 91–96%.** Treat those two days as suspect (processing lag or a tracking regression). The 30-day bounce rate is slightly inflated by them.
- `generate_lead` also fires on offer submit in code (`Analytics.offerSubmitted`). Treat the 23 leads as “listings + a possible handful of offers.”

---

## Snapshot

| Metric | 30 days |
| --- | ---: |
| Sessions | 1,798 |
| Active users | 1,614 |
| New users | 1,600 (99% of users) |
| Page views | 9,268 (5.15 per session) |
| Engaged sessions | 1,499 |
| Bounce rate | 16.6% |
| Engagement rate | 83.4% |
| Avg session duration | 156.5s (2:37) |
| `view_item` | 365 |
| `form_start` | 278 |
| `begin_checkout` | 28 |
| `generate_lead` | 23 |
| `purchase` | **1** |
| `add_to_cart` | 0 |

Sitewide bounce is healthy. People are not bouncing off the domain. They click, hop, and leave without paying or listing.

Traffic mix: **Paid Social 1,193 sessions (66%)**, Paid Search 211, Direct 96, Organic Social 91, Organic Search 69. **Mobile is 1,667 / 1,798 (92.7%)**.

---

## 1. Bottlenecks — where we lose users

**Not the FAQ. Not artist hubs.** Those two surfaces were explicitly checked.

### Ranked leaks

| Rank | Surface | Volume | Bounce | Engagement / user | What is actually happening |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | `/sell/new` | **903 sessions (50% of all traffic)** | 5.0% | 11s | Instagram dumps sellers onto a long form. 278 `form_start` → 23 leads (**97.5% drop**). |
| 2 | Event page → checkout | 242 event sessions | 7.4% | 27s | They *arrive* and look. 28 `begin_checkout` (**88.4% drop**). Zero `add_to_cart`. |
| 3 | Checkout → purchase | 28 `begin_checkout`; 11 PayMe success sessions | 0% on success URL | 30s | **1 `purchase`.** Either payment is not confirming, or tracking only fires after `status=paid` inside a 40s poll. |
| 4 | Homepage | 718 sessions, 3,017 views | **25.8%** | 10s | Largest *absolute* bounce-exit (~63 of 361 stripped landings). Survivors do navigate onward. |
| — | Artist hubs | 274 sessions, 1,324 views | **5.1%** | 24s | Throughput. Strongest internal edge is artist → event (248 sessions). |
| — | FAQ `/faq` | **17 sessions** | 11.8% | **44s** | Trust reading. Not a drop-off well. |
| — | `/how-it-works` | 3 sessions | 100% | n too small | Dead page, irrelevant volume. |

Independent buyer conversion (do **not** read as one cohort):

- Home 718 → event 242 = **33.7%** (66.3% drop)
- Event 242 → `begin_checkout` 28 = **11.6%** (88.4% drop)
- `begin_checkout` 28 → `purchase` 1 = **3.6%** (96.4% drop)

Independent seller conversion:

- `/sell/new` 903 → `generate_lead` 23 = **2.5%**
- `form_start` 278 / 903 sell sessions = 30.8% even *start* the form
- 23 / 278 form starts = 8.3% finish

### Highest landing pages (query-stripped, top-50 API rows)

Instagram `fbclid` URLs split across unique query strings, so `/sell/new` is under-counted in this table. Use the 903 family count above for volume.

| Path | Landings | Est. bounce exits | Bounce |
| --- | ---: | ---: | ---: |
| `/` | 361 | 63 | 17.5% |
| `/sell/new` | 49 | 2 | 4.1% |
| `/event/בן-צור-קיסריה-2026-07-27` | 32 | 1 | 3.1% |
| `(not set)` | 12 | 12 | 100% |
| `/dashboard` | 10 | 2 | 20% |
| `/event/מור-רביעי-תל-אביב-2026-08-13` | 9 | 1 | 11% |
| `/artist/22` | 5 | 0 | 0% |
| `/event/איתי-לוי-קיסריה-2026-08-29` | 5 | 5 | **100%** |

### Highest-bounce routes (sessions ≥ 3) — exit proxy

| Path | Sessions | Bounce | Note |
| --- | ---: | ---: | --- |
| `/how-it-works` | 3 | 100% | Ignore (n=3) |
| `/event/איתי-לוי-קיסריה-2026-08-29` | 18 | 50% | Sold-out / empty inventory feel |
| `/privacy` | 5 | 40% | Legal, not funnel |
| `/refunds` | 9 | 33% | Legal |
| `/` | 718 | 25.8% | Volume exit |
| `/event/איתי-לוי-קיסריה-2026-09-01` | 22 | 22.7% | 6s engagement — pogo |

Artist and event *family* bounce rates are 5.1% and 7.4%. Those pages are not ejecting people. They are failing to convert the people who stay.

---

## 2. Navigation flow — do users reach events?

**Yes.** The marketplace path is working. The conversion path after the event page is not.

Internal `pageReferrer` → `pagePath` edges (same-site only):

| Edge | Page views | Sessions |
| --- | ---: | ---: |
| Artist → Event | 273 | **248** |
| Home → Artist | 244 | 218 |
| Artist → Home (back out) | 252 | **171** |
| Home → Event (skip hub) | 140 | 118 |
| Event → Artist | 122 | 115 |
| Event → Home | 81 | 59 |
| Home → `/sell/new` | 24 | 19 |

`Home.jsx` `handlePerformerNavigate` uses `performerNavigateTarget`: one in-stock event deep-links to `EventDetailsPage`; several dates still go to `/artist/:slug`. That hub is **not** a trap — `/artist/10` (Eyal Golan) → `/event/אייל-גולן-תל-אביב-2026-09-08` is 45 views / 41 sessions.

What *is* leaking on the hub: **171 sessions go back to home** without opening a date. `ArtistPage.jsx` header CTA is “התראת כרטיסים” (waitlist), not a priced next show. `pickMostSupplyEventId` is already computed and used only as a “הכי הרבה כרטיסים” badge.

`/ticket/:id` and `/event-group` had **zero sessions**. `TicketSelectionPage` is unused this month.

External entry (this is the real traffic shape):

| Referrer → kind | Page views | Sessions |
| --- | ---: | ---: |
| instagram.com → `/sell/new` | 1,287 | 622 |
| instagram.com → `/sell` | 1,003 | 753 |
| www.google.com → `/` | 706 | 218 |
| instagram.com → `/` | 381 | 208 |
| Facebook (l. / m. / www.) → sell | ~400 | ~200 |
| live.payme.io → checkout | 33 | 11 |

`/sell` is `SellMarketingRedirect` in `App.jsx` (`<Navigate to=/sell/new replace />`). `PageTracker` still fires a pageview. Result: **997 sessions on `/sell` with 0.5s engagement per user** — a paid hop.

---

## 3. Engagement by route

`averageSessionDuration` with `pagePath` is session-scoped (includes the rest of the visit). **Engagement seconds per active user** is the better on-page signal.

| Path | Views | Bounce | Eng / user | Read |
| --- | ---: | ---: | ---: | --- |
| `/` | 3,017 | 25.8% | 10s | Browse then hop |
| `/sell/new` | 2,062 | 5.0% | 11s | Arrive, don’t finish |
| `/sell` | 1,368 | 4.8% | **0.5s** | Redirect tax |
| `/artist/10` Eyal Golan | 314 | 7.7% | 20s | Best hub dwell |
| `/artist/25` Peer Tasi | 303 | 1.5% | 16s | Click-through hub |
| `/artist/22` Ben Tzur | 266 | 0% | 17s | Tied to 27 Jul Caesarea |
| `/event/בן-צור-קיסריה-2026-07-27` | 178 | 3.1% | 27s | **Past date still ranking** |
| `/event/אייל-גולן-תל-אביב-2026-09-08` | 99 | 4.3% | 11s | Live inventory, thin inspect |
| `/event/אייל-גולן-תל-אביב-2026-09-06` | 51 | 16% | **43s** | Best inspect time |
| Peer Tasi Caesarea 13–25 Aug (four URLs) | ~191 | 0–4% | **4–5s** | Pogo / past dates |
| `/faq` | 48 | 11.8% | 44s | Trust, not leak |
| `/checkout/payme/success` | 35 | 0% | 30s | 11 sessions, 1 purchase event |

Healthy event exploration in this product’s own analytics comments is 2–4 minutes on `/event`. Almost no event URL is in that band except Eyal 6 Sep (43s) and a couple of concert-day pages.

---

## 4. Actionable UX / routing changes (5)

Highest conversion impact first. Each item names the files to touch.

### P1 — Kill the `/sell` hop. Make listing step 1 two fields.

**Evidence:** 903 `/sell/new` sessions, 97.5% drop to 23 leads; 753 Instagram sessions hit `/sell` first (0.5s); 278 `form_start` vs 23 completes.

**Change:**

- Point every Paid Social destination at `/sell/new` (no `/sell` hop). If `/sell` must remain, skip `PageTracker` on `SellMarketingRedirect` (`frontend/src/App.jsx`).
- `TicketUploadWizard` in `frontend/src/pages/Sell.jsx`: step 1 = artist + date only. Move section, seats, and PDF beside price. Keep `SellCompletionModal` (guest auth) *after* they have seen payout.
- Keep PDF required before publish, not before “what you’ll receive.”

The traffic is already on the form. This is not an acquisition problem.

### P2 — Always-visible “קנה עכשיו” + sticky mobile buy bar

**Evidence:** 242 event sessions → 28 checkouts (11.6%); 0 `add_to_cart`; 93% mobile. `EventDetailsPage.jsx` uses `showActions = isExpanded`. Empty inventory copy is still English: “No tickets available right now.”

**Change:**

- Render the buy CTA on the collapsed `viagogo-ticket-row`. Keep expand for map highlight / offer.
- Sticky mobile bar: lowest price + קנה עכשיו.
- Hebrew sold-out hero; `WaitlistSignupModal` as the primary action when `ticketGroups.length === 0`.
- Fire `add_to_cart` on first CTA tap so this step is visible in GA4 (`frontend/src/utils/analytics.js`).

### P3 — Confirm PayMe returns; fire `begin_checkout` when the modal opens

**Evidence:** 28 `begin_checkout`, **11 sessions on `/checkout/payme/success`**, **1 `purchase`**. `CheckoutModal.jsx` fires `checkoutStart` only after `guestCheckout` and immediately before PayMe redirect. `PaymeCheckoutSuccess.jsx` records purchase only when receipt `status` is `paid`/`completed` inside a 40s poll; guests need `sessionStorage` email for `getReceipt`.

**Change:**

- `Analytics.checkoutStart` on `CheckoutModal` mount (keep a second param for `payme_redirect`).
- Django: IPN should mark the order paid *before* the buyer lands on the success URL; persist guest email on the order so polling does not depend on `sessionStorage`.
- Success page: distinguish timeout vs unpaid instead of a silent miss.

Until this is fixed, you cannot tell “abandoned guest form” from “PayMe charged but SPA never saw `paid`.”

### P4 — Artist header: priced next date, not waitlist

**Evidence:** Artist → event already works (248 sessions). The leak is 171 sessions artist → home. `ArtistPage.jsx` header CTA is waitlist. `pickMostSupplyEventId` is already in the page.

**Change:**

- Primary header button: “כרטיסים מ-₪X” → `eventHref(mostSupplyEvent)`.
- Waitlist secondary.
- Min price on each date row.

Do not spend a sprint “fixing” artist hubs as if they were FAQ-style dead ends. They are missing a buy-shaped header.

### P5 — Django: 301 past event slugs to the next date (or artist hub)

**Evidence:** `/event/בן-צור-קיסריה-2026-07-27` is still the #3 landing in the top-50 extract (32 landings, 178 views) after the concert. Peer Tasi 13/15/20/22/25 Aug URLs still draw ~191 views at 4–5s. Itay Levi Caesarea 29 Aug: 5 landings, 100% bounce.

**Change:**

- In the event retrieve API / SPA fallback view: if `event.date` is past and a later same-artist event exists, **301** to that slug; else 301 to `/artist/:slug`.
- On `EventDetailsPage`, skip the venue map for past dates and jump to waitlist / next date.

Do not spend the 242 event sessions you do get on expired URLs.

---

## What not to do

- Do **not** redesign FAQ, `/how-it-works`, or trust pages as the conversion program. FAQ is 17 sessions with the highest healthy dwell (44s) of any content route.
- Do **not** treat homepage bounce 25.8% as “the homepage is broken.” It is the largest door. Paid Social is not even aimed at it.
- Do **not** buy more Instagram traffic to `/sell` until P1 ships. You are paying for a redirect hop plus a form nobody finishes.

---

## Instrumentation follow-ups (not UX, but they poison the funnel)

1. Fire `begin_checkout` on modal open (P3) — otherwise details → checkout mixes “never clicked buy,” “abandoned guest form,” and “PayMe bounce.”
2. `add_to_cart` is completely dark (0 events).
3. Strip `fbclid` (or send `page_location` without query) so landing reports stop fragmenting.
4. Investigate 25–26 Aug 91–96% bounce (GA4 processing vs a deploy that broke engagement hits).
5. `PageTracker` + `SellMarketingRedirect` double-counts `/sell` → `/sell/new`.
