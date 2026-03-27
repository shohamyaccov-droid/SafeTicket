# SafeTicket — Premium UX & Trust Report

**Audience:** Product, design, and engineering  
**Goal:** Elevate SafeTicket to feel **high-end, trustworthy, and premium** while reducing anxiety around money, tickets, and negotiations.

---

## Summary of fixes shipped in this cycle

| Area | Change |
|------|--------|
| Double charging | `purchase_completed` + `ticket_listing_status` on offers; UI hides **השלם רכישה** and shows **נרכש בהצלחה** when appropriate. |
| Offers history | Backend returns full offer history (no pagination cut-off); dashboard splits **קיבלתי** / **שלחתי**; mutations trigger refetch + tab refresh. |
| Fee clarity | Offer modal copy states price is **before service fee** (עמלת שירות). |
| Performance | Events/artists list queries use `select_related` / aggregates to reduce N+1; Sell page loads artists + events in parallel. |
| Tests | E2E-style API tests for `purchase_completed` after paid order and immediate visibility after new offer. |

---

## 1. Trust & clarity (highest impact)

### 1.1 Receipts and paper trail

- **Email receipt** after every successful payment: order id, event, seat/section, amounts (subtotal, service fee, total), seller snapshot, and support link.
- **In-app receipt** on the purchase detail view (print/PDF optional) with the same line items.
- **Negotiation timeline** export (optional): single PDF of the thread for disputes.

### 1.2 Human-readable status language

Replace internal states with short, calm Hebrew labels everywhere: *ממתין לאישור*, *אושר — ממתין לתשלום*, *נרכש*, *נדחה*, *פג תוקף*. Avoid raw enum strings in UI.

### 1.3 Security & compliance badges

- Footer or checkout: short copy on **PCI** (if applicable), **encrypted connection**, **seller verification** (when you add KYC tiers).
- “**למה לשלם דרך SafeTicket?**” micro-section: money held until delivery, dispute path, no off-platform payment.

---

## 2. Visual polish & motion

### 2.1 Motion (subtle, purposeful)

- **Page transitions:** 150–200ms fade/slide between dashboard tabs (not flashy).
- **Success moments:** brief checkmark animation on **נרכש בהצלחה** and after checkout.
- **Skeleton screens** instead of spinners for lists (events, offers, purchases): reduces perceived “hang” on slow networks.

### 2.2 Typography & density

- One clear hierarchy: event title > meta (date/venue) > actions.
- Generous whitespace in negotiation threads; align amounts to a **tabular** rhythm (RTL-safe).

### 2.3 Empty and loading states

- **Empty offers:** illustration + one sentence (“עדיין אין משא ומתן — גלשו לאירוע והציעו מחיר”).
- **Loading:** skeleton rows matching final card height (avoid layout shift).

---

## 3. Checkout & pricing UX

### 3.1 Fee breakdown (always visible before pay)

Show: **מחיר מוסכם** → **עמלת שירות (X%)** → **סה״כ לחיוב**. No surprise at the last step.

### 3.2 Timer anxiety

For accepted-offer checkout windows, pair the countdown with **plain text**: “אם לא תשלימו, ההצעה תבוטל והכרטיס יישאר זמין.” Reduces confusion when the timer hits zero.

---

## 4. Offers & negotiation UX

### 4.1 Persistent thread

- Keep full history visible (already aligned with product direction).
- **Pin** the latest actionable row at the top on mobile; full thread below.

### 4.2 Seller vs buyer affordances

- **Buyers** see fee-inclusive preview when relevant; **sellers** never see buyer’s total with fee in counter UI (privacy already partially enforced — extend consistently).

---

## 5. Email & notifications

- **Transactional:** offer received, offer accepted, payment reminder (T-1h before checkout expiry), payment confirmed, ticket delivered.
- **Tone:** short, confident, no exclamation spam.
- **Deep links** back to the exact offer/ticket thread.

---

## 6. Accessibility & internationalization

- Focus rings on primary actions; `aria-live` region for toast success/error.
- All fee and legal copy available in consistent Hebrew terminology (glossary: עמלת שירות, מחיר סופי, מחיר לפני עמלה).

---

## 7. Metrics to watch (product)

- Time from **accept** → **paid** (drop-off indicates timer or UX friction).
- **Double-checkout attempts** (should trend to zero with `purchase_completed` + UI lock).
- Support tickets tagged “price confusion” or “offer disappeared” (should drop after history + cache fixes).

---

## 8. Suggested roadmap (90 days)

1. Email receipts + in-app receipt PDF.
2. Skeleton loaders on Events, Dashboard, Offers.
3. Unified design tokens (spacing, radius, shadow) across modals.
4. Lightweight animation library only if bundle budget allows (or CSS-only success states).
5. Optional: trust badge strip on homepage and checkout footer.

---

*This document is meant to complement engineering fixes: same product truth, elevated presentation and reassurance.*
