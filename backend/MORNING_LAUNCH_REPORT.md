# SafeTicket — Morning Launch Report

**Generated (codebase / agent):** 2026-03-26 (local workspace)  
**Production API:** `https://safeticket-api.onrender.com/api` (default in QA scripts)

This report summarizes infrastructure hardening, security changes, QA automation added in-repo, and **what you must run on Render** to complete verification with real credentials.

---

## 1. Infrastructure & media (Cloudinary)

### Implemented in `backend/safeticket/settings.py` (existing / prior + verified)

- **`CLOUDINARY_URL`** parsed with `urlparse` + `unquote` for key/secret; **`CLOUDINARY_STORAGE`** populated with `CLOUD_NAME`, `API_KEY`, `API_SECRET` (required by `django-cloudinary-storage`).
- **Conflicting env:** when `CLOUDINARY_URL` is set, split vars (`CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`) are temporarily removed during the first `import cloudinary` so pycloudinary’s `Config()` does not mix stale split vars with the URL (a common **Invalid Signature** cause on Render).
- **`CLOUDINARY_SIGNATURE_ALGORITHM`:** optional `sha1` (default) or `sha256` for signing.
- **Startup:** `ImproperlyConfigured` if Cloudinary is enabled but credentials are incomplete.

### Your action on Render

1. Set **`CLOUDINARY_URL`** exactly as in the Cloudinary console (`cloudinary://API_KEY:API_SECRET@CLOUD_NAME`), no extra quotes or newlines.
2. Prefer **one** source of truth: either **only** `CLOUDINARY_URL`, or **only** the three `CLOUDINARY_*` variables — avoid mismatched duplicates.
3. If **Invalid Signature** persists after deploy, set **`CLOUDINARY_SIGNATURE_ALGORITHM=sha256`** once and redeploy.

---

## 2. Security & API behavior

### PDF URLs (ticket detail)

- **Change:** `TicketSerializer.get_pdf_file_url` no longer returns **raw Cloudinary (or media) URLs** to the API client.
- **Behavior:** Authorized users (seller of the ticket, staff, or buyer with a paid/completed order containing that ticket) receive the **authenticated download URL**:  
  `/api/users/tickets/<id>/download_pdf/`
- **Public / anonymous:** `pdf_file_url` is **`null`** on ticket detail; **`has_pdf_file`** is **`true`** when a PDF exists (for marketplace UI badges without leaking storage URLs).
- **`pdf_file`** on the serializer is **`write_only`** on read responses so the raw storage path/URL is not echoed.
- **Direct Cloudinary links:** Default Cloudinary delivery is often **public** if assets are not marked authenticated/private. The API no longer hands out those URLs; access for PDFs is enforced via **`download_pdf`** (IDOR checks already present in `TicketViewSet.download_pdf`).

### JWT cookies (local dev)

- **`users/authentication.py`:** When **`DEBUG=True`**, JWT cookies use **Lax + Secure=False** so browsers send cookies on `http://127.0.0.1` / localhost. Production **`DEBUG=False`** keeps **SameSite=None + Secure** for the SPA on HTTPS.

### DEBUG

- Production must keep **`DEBUG=False`** on Render (dashboard env). The QA script does not infer this from HTTP; confirm in Render **Environment**.

### Non-PDF upload

- Invalid uploads should return **400** with a clear error (not **500**). See `TicketViewSet.create` validation in `users/views.py`.

---

## 3. Performance

- **`TicketViewSet.get_queryset`:** `select_related('event', 'seller')` for public and seller ticket lists.
- **`EventViewSet.tickets`:** `select_related('event', 'seller')` on the ticket queryset.

---

## 4. Frontend (badges)

- **`EventDetailsPage.jsx`**, **`CheckoutModal.jsx`**, **`Dashboard.jsx`:** “PDF present” UI uses **`has_pdf_file || pdf_file_url`** so listings work without exposing raw Cloudinary URLs.

---

## 5. QA automation (run in CI or locally)

| Script | Purpose |
|--------|---------|
| `backend/qa_production_render_cycle.py` | Original production flow: qa_bot login → upload 2 PDFs → approve → buyer → checkout → download |
| `backend/morning_launch_qa.py` | Extended: optional **new seller** (`USE_NEW_SELLER=1`), fake-PDF rejection, anonymous ticket detail security check, profile orders, SHA-256 integrity of downloads, optional Render deploy |

### Example (PowerShell)

```powershell
$env:QA_PASSWORD="..."   # qa_bot password (from seed_production / fix_admin)
$env:API_BASE="https://safeticket-api.onrender.com/api"
# Optional: $env:USE_NEW_SELLER="1"
# Optional: $env:RENDER_API_KEY="..."  # triggers deploy + wait
Set-Location backend
python morning_launch_qa.py | Tee-Object -FilePath morning_report.json
```

### Output to capture for this report

- **`cloudinary_pdf_urls`** in JSON may now hold **API download URLs** (or legacy Cloudinary URLs from older responses); **anonymous** ticket detail must **not** include raw `res.cloudinary.com` URLs.
- **`pdf_integrity`:** `upload_source_sha256` vs per-ticket download SHA-256 must match.
- **`security.anonymous_ticket_detail`:** `pdf_file_url` should be `null`; `has_pdf_file` should be `true` after approval.

---

## 6. Render deploy (manual API)

- **Requires:** `RENDER_API_KEY` + correct service id (`RENDER_SERVICE_ID`, default in script matches prior project default).
- **If not set:** script skips deploy and notes it in JSON.

---

## 7. Bugs fixed in this pass (summary)

| Area | Fix |
|------|-----|
| API leakage | Removed raw storage URLs from ticket serializer for clients; added `has_pdf_file` |
| DB | `select_related` on hot ticket query paths |
| Dev UX | JWT cookie flags when `DEBUG=True` |
| QA | `morning_launch_qa.py` for broader launch checks |

---

## 8. Production test run (agent)

**Not executed here against live Render** (no `QA_PASSWORD` / `RENDER_API_KEY` in this environment). After you run `morning_launch_qa.py` with secrets, paste the JSON **`cloudinary_pdf_urls`**, **`pdf_integrity`**, and **`steps`** into your internal runbook.

---

## 9. Final Cloudinary URLs for test tickets

**Populate after a successful production run** from the JSON field **`cloudinary_pdf_urls`** (or from seller/admin UI if you still log raw URLs server-side). With the new serializer, **client-visible** URLs should be **`.../download_pdf/`** API paths, not `res.cloudinary.com`.

---

*End of report.*
