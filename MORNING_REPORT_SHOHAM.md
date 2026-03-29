# SafeTicket — Morning Report for Shoham (Lead Architect Sprint)

**Date:** March 28, 2026  
**Scope:** Mobile login / ITP, concurrency hardening, API throttling, UX (skeletons, empty states, toasts), PWA polish, Cloudinary + Open Graph, iPhone E2E journey.

---

## 1. Mobile login and Safari ITP (cross-domain cookies)

**Production behavior:** When `DEBUG` is false (Render), Django now applies **`CSRF_COOKIE_SAMESITE` / `SESSION_COOKIE_SAMESITE = 'None'`** with **`CSRF_COOKIE_SECURE` / `SESSION_COOKIE_SECURE = True`**, which is required for cross-site cookies between the SPA origin and the API origin in Safari.

**Local HTTP:** Defaults remain **Lax** + non-secure cookies unless **`SAFETICKET_CROSS_SITE_COOKIES=1`** is set (e.g. HTTPS tunnel).

**Token fallback:** `JWT_RESPONSE_BODY_TOKENS` (default **on** in production / cross-site dev) returns access/refresh in JSON on login/register when enabled. The frontend stores tokens via **`setBearerFallback`** in `api.js` and sends **`Authorization: Bearer`** on API calls when cookies are blocked.

**CORS:** `CORS_ALLOW_CREDENTIALS = True` with explicit allow-lists for dev and production Render origins (`safeticket-web` + `safeticket-api`), plus matching `CSRF_TRUSTED_ORIGINS`.

**Files:** `backend/safeticket/settings.py`, `backend/users/authentication.py`, `backend/users/views.py`, `frontend/src/services/api.js`, `frontend/src/context/AuthContext.jsx`.

---

## 2. Concurrency and double-booking protection

**Orders:** `create_order` and related flows already run inside **`transaction.atomic()`** with **`select_for_update()`** on tickets and offers. The negotiated **`Offer`** is loaded **inside** the same atomic block with **`select_for_update`** so two concurrent checkouts cannot corrupt state.

**Offers:** Accept/reject/counter paths lock **`Offer`** and related **`Ticket`** rows with **`select_for_update`**.

**Files:** `backend/users/views.py` (see `create_order`, `confirm_order_payment`, offer accept).

---

## 3. Enterprise throttling (DRF)

**Scoped rates** (see `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`):

- `auth_login`: 30/minute  
- `auth_register`: 20/minute  
- `offers`: 25/minute  
- `offers_mutations`: 90/minute (accept / reject / counter)

**Implementation:** `backend/users/throttles.py`; register/login and `OfferViewSet` wired in `views.py`.

---

## 4. UI: skeletons and empty states

- **Dashboard:** `DashboardSkeleton` while loading; wrapper styles in `Dashboard.css`.
- **Home (artists):** Reusable **`EmptyState`** for empty artist lists.
- **Skeleton styles:** `frontend/src/components/ui/Skeleton.css`; dashboard skeleton under `components/skeletons/`.

---

## 5. Global toasts (Hebrew, RTL)

- **Library:** `react-hot-toast` with **`<Toaster />`** in `main.jsx` and helpers in **`utils/toast.js`** (RTL styling).
- **Coverage:** Login/register, dashboard operations, checkout (payment, reserve, PDF, timeout), sell flow, home/group/artist/event/ticket pages, admin verification, profile — **user-facing errors** use **`toastError` / `toastSuccess`** instead of silent `console.error` in those paths.

**Note:** Legacy **inline `Toast`** on some pages may still exist alongside react-hot-toast; both can coexist during transition.

---

## 6. PWA and mobile polish

- **`index.html`:** Viewport includes **`maximum-scale=1`**, **`user-scalable=0`**, **`viewport-fit=cover`** to reduce iOS input zoom issues.
- **`public/manifest.json`:** Standalone display, RTL, theme colors; icon entry (SVG).
- **`apple-touch-icon`** link added (currently `vite.svg` — consider a dedicated 180×180 asset later).

---

## 7. Cloudinary URLs and Open Graph

- **`getFullImageUrl`** in `formatters.js` appends transformation segments (**`f_auto,q_auto,w_<width>,c_limit`**) for `res.cloudinary.com` upload URLs when not already transformed.
- **OG / sharing:** `og:title`, `og:description`, `og:locale`, **`og:image`** pointing to **`/og-share.svg`** (1200×630) on the web host. **`twitter:card`** = `summary_large_image`.

**Recommendation for WhatsApp:** Some clients prefer a **raster** (PNG/JPEG ~1200×630) on a CDN; upload a dedicated asset and point `og:image` there if previews are inconsistent with SVG.

---

## 8. Playwright — full iPhone-style journey

**Spec:** `e2e/iphone-full-journey.spec.js`  
**Device profile:** Playwright **`devices['iPhone 13']`** (viewport, UA, touch, `isMobile`).  
**Flow:** UI registration (seller) → upgrade to seller → list ticket with minimal PDF → admin approves via API → buyer registers → bargain offer → seller accepts → buyer checkout (mock card) → PDF download. Assertions include **Hebrew toast** copy (`נרשמת בהצלחה`, `התחברת בהצלחה`) and **buyer total math** (10% fee on negotiated base).

**Run locally:**

```bash
cd e2e
set E2E_WEB_URL=https://safeticket-web.onrender.com
set E2E_API_URL=https://safeticket-api.onrender.com
npx playwright test iphone-full-journey.spec.js
```

Requires valid **`E2E_ADMIN_USERNAME` / `E2E_ADMIN_PASSWORD`** if defaults differ on your environment.

**Spec stability (post-push):** Registration waits on **`POST` success** and URL leaving `/register` before asserting the Hebrew success toast; success toast duration was extended to **12s** so Playwright can assert it after navigation to `/`.

---

## 9. Verification performed in this workspace

- **`python manage.py check`:** OK (no DB URL in local env — expected).
- **`npm run build` (frontend):** OK.
- **`npm run lint`:** Reports many **pre-existing** prop-types / hooks warnings across the app; not introduced as a full cleanup in this sprint.

---

## 10. Deploy checklist (Render)

1. Ensure **`DEBUG=False`** on the API service.  
2. Set **`CORS_ALLOWED_ORIGINS`** / **`CSRF_TRUSTED_ORIGINS`** to the exact SPA origins (no trailing slash).  
3. For strict mobile cookie testing over HTTPS localhost tunnels, set **`SAFETICKET_CROSS_SITE_COOKIES=1`**.  
4. Optionally **`JWT_RESPONSE_BODY_TOKENS=true`** explicitly (default is already favorable off pure local HTTP).  
5. After push to **`main`**, confirm the **Render web** deploy serves new **`og-share.svg`** and updated `index.html` meta tags.

---

## 11. Known follow-ups (non-blocking)

- Replace **`vite.svg`** with a proper **app icon set** (PNG 192/512 + Apple touch).  
- Optional: unify on **only** react-hot-toast and remove legacy **`Toast.jsx`** where redundant.  
- Expand skeleton/empty-state usage on **EventDetails** / **Sell** if you want visual parity everywhere.

---

*Prepared for handoff to product and QA.*
