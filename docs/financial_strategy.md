# TradeTix — 12-month financial strategy

**Role of this memo:** Fractional CFO + data science read of the model in `scripts/financial_model.py`.  
**Planning case:** 0% seller fee, **12% buyer fee**, ₪300 average face.  
**Live product today:** 7% buyer / 0% seller (`PLATFORM_BUYER_SERVICE_FEE_RATE`, `BUYER_SERVICE_FEE_PERCENT`). Treat 12% as a *decision*, not as what checkout charges this week.  
**Volume spine:** 12 → 400 paid tickets/month (1,812 tickets year). That is a stretch from August 2026 reality (~1 tracked purchase, 23 seller leads, ~1,800 sessions) and only works if inventory quality and PayMe/`purchase` tracking are fixed first.

CSV: `scripts/financial_projection_12m.csv`  
Regenerate: `python financial_model.py --buyer-fee 0.12`  
Live-rate sensitivity: `python financial_model.py --buyer-fee 0.07`

---

## 1. Unit economics (one ₪300 ticket)

| | Planning 12% | Live 7% |
|---|---:|---:|
| Buyer pays | ₪336.00 | ₪321.00 |
| Platform take | ₪36.00 | ₪21.00 |
| PayMe (1.5% of charge + ₪1.20) | ₪6.24 | ₪6.02 |
| Contribution after PSP | **₪29.76** | **₪14.98** |
| PayMe as % of take | 17.3% | **28.7%** |

Seller fee is ₪0 in both cases. That is the brand. It also means **every shekel of growth must come from buyer take minus PSP, ads, and infra.**

SMS is not the problem: ₪0.28 × 1.3 messages ≈ ₪0.36 per signup. At month 12 that is ₪262 — less than one day of ads.

Fixed stack (Render + Postgres + Cloudinary + domain) starts ~₪358/month and steps to ~₪1,036 when traffic and PDF volume force paid tiers. **Infra never kills this business. Ads + take-rate do.**

Contribution covers fixed costs at:

- 12%: ₪358 / ₪29.76 ≈ **12 tickets/month** (we start the ramp here).  
- 7%: ₪358 / ₪14.98 ≈ **24 tickets/month**.

---

## 2. Year picture (12% planning case)

| | Year total |
|---|---:|
| Tickets sold | 1,812 |
| GMV | ₪543,600 |
| Platform revenue | ₪65,232 |
| PayMe | ₪11,307 |
| Ads (seed ₪2,000 × 3 months, then 7% of GMV) | ₪42,708 |
| EBITDA | **+₪3,402** |

Monthly EBITDA crosses zero in **month 4** (48 tickets, +₪15) and finishes month 12 at **+₪2,206**. Months 1–3 lose ~₪5.2k on purpose: that is the CMO ₪2,000/month seed from the growth blueprint, spent before GMV can carry media.

**Same tickets at live 7%:** revenue ₪38,052, same ads ₪42,708, EBITDA **−₪23,379**. Paid growth at 7% of GMV ads is mathematically larger than a 7% take after PayMe. If we keep 7% in checkout, ads after month 3 must drop to ~3.5% of GMV or unit contribution stays red.

---

## 3. Where to deploy capital (flywheel)

The flywheel is **sellers → scarce inventory → buyer intent → more sellers**. August data already showed the failure mode: 83% of Meta went to sellers on a dead Peer Tasi event; 903 `/sell/new` sessions produced 23 leads; Google buyer queries converted to sessions but not purchases.

**Spend in this order. Do not invert it.**

1. **Checkout truth (weeks, not a line item).** 28 `begin_checkout` / 11 PayMe success / 1 `purchase` means we cannot allocate media on CPA. Fix confirmation + pixels before scaling Google. This is the highest-ROI “investment” because it makes every later shekel measurable.

2. **Seller ads only against sold-out / waitlist events (inventory).** CPL ~₪55 is acceptable if the listing is for an event that already has search demand (`איתי לוי`, `אייל גולן`, EuroLeague, מכבי). Cap seller CAC in the model at ₪55; kill campaigns whose landing event has no waitlist and no Google query volume.

3. **Google buyer capture once a given event has ≥3 live listings.** Buyer CAC in the model is ₪38. That only works if the event page shows a real **קנה עכשיו**. Sending buyer traffic to empty inventory is lighting money on fire (same mistake as Peer Tasi, flipped).

4. **Do not buy more homepage traffic.** Homepage is not the bottleneck. Event-level intent is.

Seed budget (months 1–3): **₪2,000/month** split ~40% Google buyers on in-stock sold-out names, 25% Meta buyers, 15% Meta sellers on waitlist events, 10% exact-match seller search, 10% retargeting waitlist/checkout. After month 3, hold **ads ≤ 7% of GMV** so media stays under ₪29.76 contribution.

That 7% cap is the flywheel governor: inventory ads create listings; listings unlock buyer ads; buyer ads must not eat the take.

---

## 4. When PayMe becomes the bottleneck

PayMe is **₪6.24 per ₪300 ticket at 12%** (₪6.02 at 7%). It is not painful at 12 tickets. It becomes a **conversation, not a crisis**, when either:

| Trigger | Planning case |
|---|---|
| Monthly PSP ≥ ₪2,000 | **Month 11** (330 tickets, ₪2,059) |
| Annual PSP | ₪11,307 — enough to ask for a published SME schedule |
| Share of take ≥ 22% | Already true **at 7% live** (28.7%). Never true at 12% (stays 17.3%) |
| Ticket mix shifts cheaper | On a ₪120 ticket, ₪1.20 fixed + 1.5% is a much larger bite of a 12% take |

**Negotiate at month 8–9** (175–220 tickets, ~₪1.1–1.4k PSP), not after month 11. Bring: trailing 90-day charge volume, Apple Pay share, refund rate, and a request for **1.1% + ₪0.90** or a blended cap. Every 0.2pp off the variable rate at month-12 volume (400 × ₪336) is ~₪269/month.

Do **not** switch PSPs just to shave 10 agorot while escrow and Hebrew support still matter. Do **not** pass PayMe through to sellers — that breaks the 0% promise.

If we stay on 7%, PayMe is already the bottleneck *as a share of take*. Raising buyer fee to 10–12% on high-demand events is a cleaner lever than begging for 20bp.

---

## 5. Two revenue streams that are not a buyer-fee hike

These sit **beside** the 0% seller / buyer-fee core. They must not look like a hidden seller commission on the sale price.

### A. Promoted listings (inventory ads, paid by the seller)

A seller who already listed for free can pay to pin the row on a sold-out event page (“הצג ראשון ל־7 ימים”).

- Price: ₪49 / 7 days on mid events, ₪99 on Menora / Bloomfield / EuroLeague.  
- Not a % of face, so the 0% story stays intact.  
- At 960 listings in month 12, if **8%** promote at ₪70 average = **₪5,376 extra** — more than that month’s Cloudinary + domain.  
- Only show promote after publish succeeds (post-`generate_lead`). Selling boosts on an empty form is the Peer Tasi mistake again.

### B. Demand packs for promoters and venues

TradeTix already sees waitlists, sold-out scans, and (soon) `begin_ticket_upload`. Package that as a monthly **“חסר לכם מלאי”** report + optional official leftover allotment:

- ₪1,500–₪4,000/month per promoter for waitlist + geo demand on their tour.  
- Or a 5–8% **official** allotment fee when the promoter dumps last-row inventory (disclosed, not peer-to-peer). That is a different product from SafePay C2C.

Promoted listings print cash this quarter. Demand packs print relationships that refill the flywheel without Meta.

---

## 6. Decisions I would take this week

1. **Model 12% for planning; if checkout stays at 7%, cut post-seed ads to ~3.5% of GMV or accept a ~₪23k year hole.**  
2. **Do not raise seller fee.** The 0% line is the only durable wedge vs Viagogo.  
3. **Lock ads: ₪2k × 3 months, then 7% of GMV, sellers only on events with waitlist or live listings.**  
4. **Book a PayMe rate call at 150+ tickets/month** (model month 8), target 1.1% + ₪0.90.  
5. **Ship promoted listings before any B2B PDF.** It is one checkout SKU and does not touch escrow.

Escrow (36h post-event) is a **working-capital** feature, not revenue. Do not spend the float. Do not book it as income.

---

## 7. How to rerun

```powershell
cd C:\Users\user\Desktop\SafeTicket\scripts
python test_financial_model.py
python financial_model.py --buyer-fee 0.12 --output financial_projection_12m.csv
python financial_model.py --buyer-fee 0.07 --avg-ticket 300
```

Assumptions live at the top of `Assumptions` in `financial_model.py` (PayMe 1.5% + ₪1.20, SMS, Render/DB/Cloudinary steps, seller CAC ₪55, buyer CAC ₪38).
