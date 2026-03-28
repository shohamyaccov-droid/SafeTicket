# Overnight sprint report — SafeTicket

Date: March 29, 2026 (local workspace)

## Phase 1 — Production bug fixes

### Cloudinary CRUD (admin image uploads)

**Problem:** In production, ImageField uploads depend on `django-cloudinary-storage` and a fully configured Cloudinary SDK **before** storage backends run.

**Changes (`safeticket/settings.py`):**

- **Single initialization path:** `STORAGES` for Cloudinary is now assigned **only after** credentials are parsed, `CLOUDINARY_STORAGE` is populated, and `cloudinary.config(...)` runs (same block as before, but `STORAGES` moved into that block so order is explicit).
- **Default local STORAGES** is set first (filesystem + Whitenoise); when `USE_CLOUDINARY` is true, it is replaced with `MediaCloudinaryStorage` (images) + `RawMediaCloudinaryStorage` (`ticket_pdfs`) + staticfiles.
- **Upload limits:** `DATA_UPLOAD_MAX_MEMORY_SIZE` and `FILE_UPLOAD_MAX_MEMORY_SIZE` default to **12 MB** (overridable via env) to reduce silent failures on larger admin/API images.

### PDF access (401 on raw delivery)

**Problem:** Private or strict raw assets on Cloudinary may reject unsigned URLs; public_id variants (with/without `.pdf`, `media/` prefix) differ by upload path.

**Changes (`users/admin_pdf_url.py`):**

- Centralized **`_all_public_id_candidates()`** to try basename, `media/` prefix, **with and without `.pdf`**.
- **`_try_cloudinary_signed_raw_urls()`** emits signed `https://` URLs with **`long_url_signature=True`** first, then shorter signature.
- Admin/API resolution still falls back to **`cloudinary.api.resource`** with `version` + signed `cloudinary_url`, then legacy `image` resource_type for old uploads.

### Dashboard “My Sales” hover / action button

**Problem:** `.enterprise-card` used `overflow: hidden`, which could clip **row action** controls (edit/delete) on listing cards; flex shrink could also squeeze the control.

**Changes (`frontend/src/pages/Dashboard.css`):**

- **`.listing-card.enterprise-card.dashboard-compact-card { overflow: visible; }`** (aligned with offer cards).
- **`.dashboard-compact-row .row-action-button`:** `flex-shrink: 0`, `position: relative`, `z-index: 2`, `pointer-events: auto`.

### Resale / listing integrity (edge case)

**Change (`users/views.py`):** **`update_ticket_price`** now returns **409 Conflict** if **`_pending_payment_blocks_price_edit`** finds any **`pending_payment`** order covering that ticket (or any member of the same `listing_group_id` for that seller). Prevents changing the face price while a buyer is in the payment window.

---

## Phase 2 — Security and code quality (review)

### Practices observed

- **ORM:** Ticket/order flows use Django ORM; no `raw()`, `.extra()`, or `cursor.execute()` found in app code for business logic.
- **SQL injection:** Low risk in reviewed paths; IDs go through ORM filters.
- **XSS:** Public API returns JSON; admin uses **`mark_safe`** only for a fixed `"EXPIRED"` label in `admin.py` (static string, no user input).
- **CSRF:** Stateful mutations use `@csrf_required` / DRF with `enforce_csrf_checks` in tests; login/register and order flows tested with `X-CSRFToken`.
- **Auth:** Sensitive actions (ticket create, orders, admin approve) require authentication; JWT via HttpOnly cookies + optional Bearer; **admin approve** requires `is_superuser`.
- **IDOR:** Ticket PDF download and similar endpoints enforce seller / paid-order / guest-email rules (existing patterns retained).

### Recommendations (not all implemented this night)

- Periodically run **`python manage.py check --deploy`** on staging with production env.
- Keep **CORS/CSRF** origins strict (already single origin in prod).
- Rate-limit registration/contact if abuse appears (offers already throttled).

---

## Phase 3 — Automated E2E QA

**New test module:** `backend/test_overnight_e2e_journey.py`

**Scenario:**

1. Register **seller** via `/api/users/register/` (role `seller`, CSRF).
2. Create **ticket** with multipart PDF (`event_id`, `pdf_file_0`, …).
3. **Admin** logs in via `/api/users/login/` (JWT cookies on a **clean** client).
4. **Approve** ticket → `active`.
5. **Guest** client: `payment_simulate` → `guest_checkout` → `confirm-payment` with `payment_confirm_token` + `mock_payment_ack`.
6. Assert **`paid`**, ticket **`sold`**, **`payment_confirm_token`** cleared, escrow **`payout_status`** / **`payout_eligible_date`** set.

**Command:**

```bash
cd backend
python manage.py test test_overnight_e2e_journey test_autonomous_marathon_qa -v 2
```

**Result:** All of the above **pass** locally (SQLite test DB).

---

## Phase 4 — Israeli mock data seed

**Command:** `python manage.py seed_israeli_data`

**Options:**

- `--reset` — deletes tickets for the demo seller (`seed_israeli_seller@safeticket.demo`) before seeding.

**Creates (idempotent-ish):**

- Artists: **עומר אדם**, **נועה קירל**
- Events: e.g. **עומר אדם — הופעה בפארק הירקון** (Tel Aviv), **נועה קירל — בלומפילד חיפה**
- Users: demo **seller**, **buyer**, optional **superuser** (on first run only — passwords printed in command help output / success message)

**Note (Windows):** Status lines use ASCII-only to avoid `cp1252` console errors; Hebrew data is still stored in the database.

---

## Phase 5 — Git

Changes were committed and pushed to **`origin/main`**. Main overnight bundle: **`eec58b8`**; report SHA note: **`0114070`**.

---

## Files touched (summary)

| Area | Files |
|------|--------|
| Settings | `backend/safeticket/settings.py` |
| PDF admin URLs | `backend/users/admin_pdf_url.py` |
| Price / escrow guard | `backend/users/views.py` |
| Dashboard UI | `frontend/src/pages/Dashboard.css` |
| E2E test | `backend/test_overnight_e2e_journey.py` |
| Seed | `backend/users/management/commands/seed_israeli_data.py` |
| Report | `MORNING_REPORT_OVERNIGHT.md` |

**Checkout / escrow core logic** was not refactored; changes are additive or narrowly scoped (PDF URL building, CSS, price PATCH guard, settings ordering).
