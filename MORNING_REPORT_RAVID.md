# SafeTicket — Morning Report for Ravid (Bearer-first mobile + imagery + performance)

**Date:** March 28, 2026  

---

## 1. Mobile blocker: JWT Bearer first (cookies unreliable on iOS Safari CORS)

**Frontend (`frontend/src/services/api.js`)**

- Access and refresh tokens are stored in **`localStorage`** (`safeticket_jwt_access`, `safeticket_jwt_refresh`).
- **`getEffectiveBearerAccess()`** resolves memory → localStorage so every Axios request sends **`Authorization: Bearer …`** after reload.
- **`setBearerFallback` / `clearBearerFallback`** keep memory and localStorage in sync (logout clears both).
- **Multipart ticket upload** uses the same Bearer resolution and, on 401, parses **`/users/token/refresh/`** JSON to update stored tokens before retry.
- **401 interceptor** persists rotated refresh (`refreshRes.data.refresh || prior refresh`).

**Backend (`backend/safeticket/settings.py`)**

- **`DEFAULT_AUTHENTICATION_CLASSES`** order is now **`JWTAuthentication` first**, then **`JWTCookieAuthentication`** (header wins at framework level; cookie remains fallback for same-site).
- **`JWT_RESPONSE_BODY_TOKENS`** defaults to **`true`** so login/register always return **`access`** (and refresh when applicable) unless explicitly disabled via env.

**Existing** `JWTCookieAuthentication` still supports HttpOnly cookies as a second factor; **primary path for cross-origin mobile is Bearer + localStorage**.

---

## 2. Omar Adam / Cloudinary URL helper

**Bug:** A naive `replace('/image/upload/', '.../f_auto,...')` could interact badly with Cloudinary segments (`v123`, folders).  

**Fix (`frontend/src/utils/formatters.js`)**

- Only rewrite URLs matching **`https://res.cloudinary.com/.../image/upload/`** (resource type **image** + **upload**).
- Insert **`f_auto,q_auto,w_<max>,c_limit/`** immediately after `upload/`, before version or public_id.
- **Skip** if the first path segment already contains a comma (typical transformation chain) or looks like an existing delivery flag (`f_`, `q_`, `w_`, `c_`, etc.).

**Artist imagery in dashboard orders**

- **`ProfileOrderSerializer.get_event_image_url`** now uses **`event_effective_image_field`**: event image, else **artist cover / artist image** (e.g. Omar Adam when the event has no dedicated image).

**Query optimization:** `build_profile_orders_serialization_context` and ticket cache use **`select_related(..., 'ticket__event__artist')`**. **`OrderSerializer` / `ProfileOrderSerializer`** ticket fallbacks use **`event__artist`** on cache miss.

---

## 3. Dashboard “thread” UX (seller)

- The **action-required banner** is a single **`button.action-required-banner-thread`**: click switches to **הצעות מחיר**, refreshes offers, and opens **`NegotiationModal`** for the first ticket group with a pending **seller** (or buyer) action.
- Copy highlights **“התקבלו N הצעות מחיר”** when only inbound offers need a reply.

---

## 4. Server-side / N+1

- **`order_receipt`**: **`select_related('ticket', 'ticket__event', 'ticket__event__artist')`** for both authenticated and guest lookups.
- **`OfferViewSet`**: added **`ticket__event__artist`** to **`select_related`**.
- Profile/dashboard helpers already batched orders + tickets; extended as above.

*(There is no `OrderViewSet` in this codebase — orders use function views; those paths were optimized where hot.)*

---

## 5. Playwright: iPhone 14 + stripped API `Set-Cookie`

**New file:** `e2e/iphone14-safari-bearer-journey.spec.js`

- Device: **`devices['iPhone 14']`**.
- **`beforeEach`**: routes API **`…/api/**`** and drops **`set-cookie`** from responses so the browser cannot rely on auth/session cookies from the API host — the app **must** use **JSON JWT + Bearer + localStorage**.
- Asserts **`regJson.access`** and **`localStorage.safeticket_jwt_access`** after register.
- Listing flow: **concert** category, prefers **Omar Adam** (or similar) in **#artist_select** when present.
- Event page: header image must **`naturalWidth > 0`** and not **via.placeholder**.
- Bargain / accept / checkout / PDF same as full journey; tries **clickable thread banner** first on seller dashboard.

**Run**

```bash
cd e2e
set E2E_WEB_URL=https://safeticket-web.onrender.com
set E2E_API_URL=https://safeticket-api.onrender.com
npx playwright test iphone14-safari-bearer-journey.spec.js
```

---

## Deploy notes

- No change required on Render for Bearer: ensure **`JWT_RESPONSE_BODY_TOKENS`** is not forced to `false`.
- After deploy, hard-refresh the SPA and verify **`localStorage.safeticket_jwt_access`** appears after login on real iOS Safari.

---

*End of report.*
