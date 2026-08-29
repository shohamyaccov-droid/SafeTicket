# TradeTix AI SEO audit — buyers, sellers, and crawlers

This document records the platform-wide LLM-SEO / SGE pass: semantic HTML, Schema.org injections, heading hierarchy, and route-level meta. The goal is that Google AI Overviews and traditional crawlers can extract **who, what, when, where, price, and how** without executing the React tree.

Crawler-visible HTML is still injected server-side (Django `spa_index_view` + `frontend/seo-server.mjs`). Client `PageSeo` / `JsonLdScript` cover hydrated sessions and Helmet-capable bots.

---

## Buyer side (events & tickets)

### Schema injections

| Surface | Schema | Source | What AI extracts |
|---|---|---|---|
| `/event/:slug` | `Event` + nested `Offer` / `AggregateOffer` | Django `build_event_json_ld()` (API `json_ld`). Client fallback: `buildClientEventJsonLd(event, tickets)` when the API omits JSON-LD. | Event name, `startDate`, `Place` (venue + city + country), ticket `availability` (`InStock` / `SoldOut`), `lowPrice` / `highPrice` / `offerCount`, currency. |
| `/event/:slug` | `BreadcrumbList` | Django `breadcrumb_json_ld` on the SEO payload **and** client `PageSeo` breadcrumbs: Home → Artist (when present) → Event. | Site architecture: marketplace → artist hub → event. |
| `/artist/:slug` | `MusicGroup` + `BreadcrumbList` | Existing artist JSON-LD; new Home → Artist crumbs. | Artist name and upcoming dates, plus hierarchy. |
| `/ticket/:id` | `Event` + `Offer` | Client `buildTicketOfferJsonLd()` (listing is user-specific; `noindex, follow`). | Single-offer price, currency, stock, venue, date. |
| `/event-group/:name` | Title + description + `BreadcrumbList` | Client `PageSeo`. | Event-name cluster in the architecture. |
| `/` | `WebSite` + `BreadcrumbList` | Server + client. Home crawler HTML now includes a numbered 3-step list (חיפוש → אימות → כניסה). | Brand, language (`he-IL`), buyer journey. |

Event crawler snapshot (`crawler_html`) is no longer a title-only stub. It is an `<article>` with:

1. Visible breadcrumb `<nav><ol>`
2. One `<h1>` = **event name** (not the SERP title)
3. `<section><h2>פרטי האירוע</h2>` with date, venue, availability count, and “מחיר מ-”
4. The SEO description paragraph

`inject_seo_into_html` now emits **multiple** JSON-LD scripts: primary (`tradetix-jsonld`), breadcrumbs (`tradetix-breadcrumb-jsonld`), and optional `extra_json_ld`. The Event API still returns `@type: Event` (not `@graph`) so existing rich-result tests stay valid.

### Semantic HTML & headings

- Event page root is `<article class="event-details-container">`. Hero is `<header>` + `<section>`; tickets live in `<section aria-labelledby="event-tickets-heading">`; venue map is `<aside>`.
- One `<h1>` (event name). Details and ticket list are `<h2>`. Map heading is `<h3>` so it nests under tickets.
- Home hero steps are a real `<ol>` (not `role="list"` on divs). Discover rows stay `<section>` with `<h2>` carousel titles. Results wrap is `<section aria-label="אירועים ואמנים">`.
- Artist page is `<article>` with `<header>` and `<section>` for upcoming dates.
- Ticket page is `<article>` with details `<section>` and map `<aside>`.
- Event-group page is `<article>` with existing header/list sections.
- App chrome already provides the single `<main>` — pages do **not** nest another `<main>`.

### Meta & accessibility (buyer)

- Event, artist, home, event-group, ticket, FAQ, legal, and contact routes all set dynamic `<title>` + `<meta name="description">` (Helmet + server inject).
- Event hero image `alt` is descriptive (`כרטיסים ל{name} ב{venue}`). Artist images already had `alt={artistName}`.
- Back / refresh / waitlist / quantity / checkout CTAs have `aria-label`s. Missing-event state is `noindex` and uses an `<h1>`.

---

## Seller side (acquisition & trust)

### Schema injections

Exact seller FAQ copy (0% fees, mandatory phone verification, SafePay escrow) is reused from `frontend/src/content/how-to-sell.json`:

1. **איך למכור כרטיס להופעה בצורה בטוחה?** — SafePay holds funds until after the show.
2. **כמה עולה למכור כרטיס להופעה יד שנייה?** — 0% seller fee.
3. **איך נמנעים מנוכלים במכירת כרטיסים?** — mandatory phone + email verification.

| Surface | Schema | Notes |
|---|---|---|
| `/how-to-sell` | `FAQPage` + `HowTo` + `BreadcrumbList` | Unchanged Q&As; crumbs added. |
| `/how-it-works` | Existing HowTo `@graph` (sell + buy) **plus** the same `FAQPage` as `extra_json_ld` | Seller trust answers now appear on the “how it works” crawl. Numbered `<ol>` sell/buy steps were already in place. |
| `/sell/new` | `FAQPage` + `BreadcrumbList` | Server crawler HTML: one `<h1>` (“מכירת כרטיס ב-TradeTix”), numbered 3-step `<ol>`, FAQ `<h2>`s. Client injects the same FAQ JSON-LD on the live wizard. |

### Semantic HTML & numbered how-tos

- Sell wizard heading is now the page `<h1>` (“תהליך הצעת כרטיס מאובטח”).
- Immediately under it: `<section><h2>איך למכור כרטיס ב-3 צעדים</h2><ol>` with the three how-to-sell steps (upload → phone verification → SafePay payout).
- Trust strip stays a `<ul>` of benefits (not a procedure).
- Listing-success view uses `<h1>` (“הכרטיס הועלה בהצלחה!”).
- `/how-it-works` sell and buy sections remain strict `<ol><li>`; the “why TradeTix” block stays `<ul>`.

---

## Meta on every public (and account) route

`frontend/src/content/static-page-meta.json` is the shared title/description catalog. Django `get_static_page_seo()` and Node `getStaticPageSeo()` both load it, so `/about`, `/terms`, `/privacy`, `/refunds`, `/buyer-guarantee`, `/accessibility`, `/contact`, and `/sell/new` now have crawler-injected title, description, `WebPage` or `FAQPage` JSON-LD, breadcrumbs, and a one-`<h1>` article snapshot.

| Route | Indexing | Heading |
|---|---|---|
| `/`, `/event/*`, `/artist/*`, marketing & legal | `index, follow` | Single `<h1>` |
| `/login`, `/register` | `noindex, nofollow` | `<h1>` (was `<h2>`) |
| `/dashboard`, `/profile` | `noindex, nofollow` | Existing `<h1>` |
| `/ticket/:id` | `noindex, follow` | Event name `<h1>` |
| 404 / missing event | `noindex` | `<h1>` |

Legal pages wrap copy in `<article class="terms-card">` (same visual class). Contact is `<article>` with a labeled submit button.

---

## Files touched (high signal)

**Shared:** `PageSeo.jsx` (breadcrumbs + robots), `EventJsonLd.jsx` (client fallback), `BreadcrumbNav.jsx`, `breadcrumbSeo.js`, `eventJsonLdClient.js`, `static-page-meta.json`, `staticPageMeta.js`, `staticPagesSeo.js`, `seo-server.mjs`.

**Backend:** `users/seo.py` (`build_breadcrumb_json_ld`, richer event crawler HTML, extra JSON-LD scripts, static-route catalog including `/sell/new`), `users/tests/test_event_seo.py`.

**Buyer UI:** `EventDetailsPage.jsx`, `Home.jsx`, `ArtistPage.jsx`, `TicketSelectionPage.jsx`, `EventGroupPage.jsx`, `FAQ.jsx`.

**Seller UI:** `Sell.jsx`, `HowItWorksPage.jsx`, `HowToSellPage.jsx`, `ListingCreatedSuccessView.jsx`.

**Meta / a11y:** About, Terms, Privacy, Refunds, Buyer Guarantee, Accessibility, Contact, Login, Register, NotFound, Dashboard, Profile.

---

## What we deliberately did not do

- Did **not** rewrite every presentational `<div>` in maps, dashboards, or admin. Those surfaces are app chrome, not SGE landing pages.
- Did **not** change the Event API `json_ld['@type']` to `@graph` (would break rich-result consumers and tests). Breadcrumbs are a **sibling** script.
- Did **not** nest `<main>` under `AppChrome`.
- Did **not** index login, register, dashboard, profile, or individual ticket checkout URLs.

---

## Verification

- Frontend unit tests: breadcrumb builder, Event/Offer fallback, HowItWorks / HowToSell / Sell / Ticket / Artist / Dashboard pages.
- Django: `users.tests.test_event_seo` (Event + AggregateOffer unchanged; BreadcrumbList + priced crawler HTML; `/sell/new` FAQ + `<ol>`).
- Production build: `frontend` `npm run build`.
