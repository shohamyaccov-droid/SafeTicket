# Mobile Night Audit — Launch Readiness (April 5, 2026)

## Scope

Mobile web UX for negotiation and listing, homepage performance tweaks, and automated international (USD) negotiation + fee/idempotency checks.

## Task 1 — Negotiation modal (mobile)

- **Keyboard / viewport:** `NegotiationModal` scrolls the footer and counter input into view on focus and on `visualViewport` resize so the submit control stays reachable when the on-screen keyboard opens.
- **Tap targets:** Primary actions use a shared class with **minimum height 48px** on mobile.
- **iOS zoom:** Counter-offer and related inputs use **font-size ≥ 16px** where applicable.

## Task 2 — Sell ticket (mobile)

- **Attachment preview:** After choosing a PDF or image, `TicketAttachmentPreview` shows a small image thumbnail or a PDF badge with a “ready to upload” label.
- **Upload feedback:** While the listing request runs, a fixed overlay shows a spinner, short copy, and an indeterminate progress bar (styles in `Sell.css`).

## Task 3 — E2E (international stress & flow)

Module: `backend/test_international_launch_e2e.py`

- **`test_usd_full_negotiation_counter_accept_pay_and_fee_breakdown`:** US listing → buyer offer → seller counter → buyer accepts (with three sequential accept POSTs: first `200`, next two `400`) → create order with correct total (`base × 1.10`) → confirm payment → asserts **buyer fee 10%**, **seller fee 5%**, net seller, currency **USD**, and **exactly one** paid order for that buyer/ticket.

## Task 4 — Performance & layout

- **Lazy images:** Home carousel cards already use `loading="lazy"` on `<img>`.
- **Horizontal scroll:** `.home-container` uses `overflow-x: hidden` under **768px** to reduce page-level horizontal bleed on small screens (intentional horizontal scroll remains only inside pill/carousel tracks where needed).

## Task 5 — Verification

- Tests: `python manage.py test test_international_launch_e2e.InternationalLaunchE2ETest -v 2` — **OK** (2026-04-05).

## Files touched (this audit batch)

- `frontend/src/pages/Sell.css` — preview + upload overlay styles.
- `frontend/src/pages/Home.css` — mobile overflow + hero search `1rem` on small breakpoints.
- `backend/test_international_launch_e2e.py` — USD full negotiation + triple-accept guard + fee assertions.

Earlier in the same initiative: `NegotiationModal.jsx/css`, `Sell.jsx`, `Dashboard.jsx` (accept debounce).
