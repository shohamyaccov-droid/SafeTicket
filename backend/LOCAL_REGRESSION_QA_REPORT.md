# Local regression QA — SafeTicket (2026-03-28)

## Environment

- **Backend:** Django `manage.py` on SQLite (no `DATABASE_URL`); `DEBUG=True`, Cloudinary **off** locally (filesystem `MEDIA`).
- **Automated checks:** `python manage.py test test_autonomous_marathon_qa -v 2` (passes).

## Step A — Artist image upload persistence

**Action:** Programmatic save of a minimal PNG to `Artist.image` via `FileField.save(...)`, then reload from DB.

**Result:** **Pass.** `artists/images/qa_regression.png` stored; `Artist` reload shows the same `image.name`.

**Render / production:** Ensure **one** consistent credential source: either full `CLOUDINARY_URL` **or** all of `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` in sync with the Cloudinary dashboard. Mismatched split vars + URL caused signature/upload issues per `settings.py` comments.

## Step B — Guest checkout → `pending_payment` → confirm → `paid`

**Action:** Exercise the same flow as the marathon QA tests: CSRF GET → POST `/api/users/orders/guest/` → POST `/api/users/orders/<id>/confirm-payment/` with `mock_payment_ack` and matching `guest_email`.

**Result:** **Pass.** Create response includes `payment_confirm_token` and `status: pending_payment`; confirm response has `status: paid`. Second guest purchase on the same listing fails as expected (inventory guard).

**Frontend:** `CheckoutModal.jsx` now refreshes CSRF before confirm, sends `payment_confirm_token` when the API returns it, optional `VITE_MOCK_PAYMENT_WEBHOOK_SECRET` for environments where `MOCK_PAYMENT_WEBHOOK_SECRET` is set, and shows distinct loading copy for order creation vs payment confirmation.

## PDF admin / Cloudinary

- `get_ticket_pdf_admin_url` uses `cloudinary_url(..., resource_type='raw', sign_url=True, secure=True)` via explicit `from cloudinary.utils import cloudinary_url`.

## API image URLs

- `absolute_file_url` and serializers using `resolved_image_url` prefer signed **https** Cloudinary image URLs when `USE_CLOUDINARY` is true, with fallback for relative `FieldFile.url` values.
