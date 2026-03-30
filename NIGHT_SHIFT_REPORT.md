# Night shift report — TradeTix frontend (QA & security)

**Date:** 2026-03-30 (session)  
**Branch:** `main` (post-push)

## 1. UI — Trust ribbon (How it works)

| Check | Result |
|-------|--------|
| Section moved under hero | **Pass** — slim horizontal ribbon inside `hero-search-section`, no separate full-width block |
| Copy (Search → Verify → Enter) | **Pass** — Hebrew: **1. חיפוש** → **2. אימות** → **3. כניסה** with inline SVG icons |
| Visual blend | **Pass** — `rgba(0,0,0,0.22)` + `backdrop-filter`, top border radius, inset highlight |

## 2. Carousel — RTL / scrollLeft

| Check | Result |
|-------|--------|
| Root cause | RTL containers use negative or inverted `scrollLeft` in some browsers, breaking prev/next |
| Fix | **Pass** — `.home-carousel-scroll` uses **`direction: ltr`** + **`flex-direction: row-reverse`** so `scrollLeft` is always **0 … max** |
| Initial view | **Pass** — `useLayoutEffect` sets `scrollLeft = max` so head of list (visual right) is visible |
| Buttons | **Pass** — `goNext` → `scrollBy({ left: -step })`, `goPrev` → `+step`; arrows hide at `canPrev`/`canNext` |

## 3. Security audit

| Item | Result |
|------|--------|
| Hardcoded API keys in `frontend/src` | **None found** — only `import.meta.env.VITE_*` (expected public build-time vars) |
| `VITE_MOCK_PAYMENT_WEBHOOK_SECRET` | Used only when set in env; must not be a production secret in repo |
| Auth refresh failure | **Fixed** — on 401 after failed refresh, **`clearBearerFallback()`** then redirect to `/login` (stale JWT cleared) |

**Automated scan:** `node scripts/night-shift-qa.mjs` — static regex scan for PAT/Stripe/Google key shapes.

## 4. Checkout / Buy hardening

| Item | Result |
|------|--------|
| Guest contact | **Pass** — email shape + 9–15 phone digits before continuing |
| Mock payment fields | **Pass** — cardholder length, 13–19 digits + **Luhn**, MM/YY not in past, CVV 3–4 digits |
| Rapid “קנה עכשיו” | **Pass** — `buyOpeningRef` blocks re-entrancy until `fetchTickets` + modal open completes |

## 5. Auth edge cases

| Item | Result |
|------|--------|
| Expired access + failed refresh | Tokens cleared; user sent to login (no orphan Bearer) |
| `getProfile` 401 | Still rejects without redirect loop (unchanged interceptor behavior) |

## 6. Self-identified fail points addressed

1. **Carousel “Next” broken in Hebrew** — normalized scroll model (ltr + row-reverse + snap to head).  
2. **Double-submit on Buy** — in-flight guard on `handleBuy`.  
3. **Stale session after refresh failure** — `clearBearerFallback()` before redirect.

## 7. Product / branding

| Item | Result |
|------|--------|
| TradeTix in shell pages / modals / legal | Consistent (`Navbar`, `Footer`, `Home`, `CheckoutModal`, Terms/Refunds/Sell, etc.) |
| Compact cards readability | Title bumped to **0.9rem**; contrast and line-height preserved |

## 8. Ultra-wide / foldable layout

| Item | Result |
|------|--------|
| Main overflow | `App > main` already `overflow-x: hidden` + safe-area on mobile |
| Super-wide monitors | **Pass** — `@media (min-width: 2200px)` caps `.App` at **2100px** centered |

## 9. Manual / suggested follow-ups (not automated here)

- Run **Playwright/Cypress** against staging for full E2E (search empty state, purchase path).
- Test **physical devices**: foldable narrow inner display; verify hero + trust ribbon on inner screen width.
- **WhatsApp / OG**: consider **PNG** `og:image` if SVG previews fail on some crawlers.

## 10. Build

- `npm run build` (Vite) completed successfully after changes.

---

*This report documents checks run or code-path fixes applied in this night-shift iteration.*
