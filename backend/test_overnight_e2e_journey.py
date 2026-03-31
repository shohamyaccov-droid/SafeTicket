"""
Overnight E2E: register (seller) → list ticket (PDF) → admin approve → guest checkout → confirm → paid + escrow.

Run: python manage.py test test_overnight_e2e_journey -v 2
"""

import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils import timezone
from datetime import timedelta

from django.contrib.auth import get_user_model
from users.models import Artist, Event, Order, Ticket

User = get_user_model()


def _minimal_pdf_bytes():
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


class OvernightE2EJourneyTest(TestCase):
    """Simulates core marketplace flow without a browser."""

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        future = timezone.now() + timedelta(days=60)
        self.artist = Artist.objects.create(name="E2E Artist")
        self.event = Event.objects.create(
            name="E2E לילה — פארק הירקון",
            artist=self.artist,
            date=future,
            venue="אחר",
            city="תל אביב",
        )
        self.admin = User.objects.create_superuser(
            username="admin_e2e_overnight",
            email="admin_e2e_overnight@test.local",
            password="AdminPass123!",
        )

    def _csrf_token(self, client=None):
        c = client or self.client
        r = c.get("/api/users/csrf/")
        self.assertEqual(r.status_code, 200, r.content)
        tok = r.cookies.get("csrftoken")
        self.assertIsNotNone(tok)
        return tok.value

    def test_register_list_ticket_approve_guest_buy_paid(self):
        # --- Register seller (JWT cookies on client) ---
        csrf = self._csrf_token()
        reg = self.client.post(
            "/api/users/register/",
            data=json.dumps(
                {
                    "username": "seller_overnight_e2e",
                    "email": "seller_overnight_e2e@test.local",
                    "password": "SellerPass123!",
                    "password2": "SellerPass123!",
                    "role": "seller",
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(reg.status_code, 201, reg.content.decode())

        # --- Create listing (pending_approval for IL / per geo rules) ---
        csrf = self._csrf_token()
        pdf = SimpleUploadedFile(
            "overnight_e2e.pdf",
            _minimal_pdf_bytes(),
            content_type="application/pdf",
        )
        receipt = SimpleUploadedFile(
            "overnight_receipt.pdf",
            _minimal_pdf_bytes(),
            content_type="application/pdf",
        )
        # Multipart: include file in data (Django test client); not as separate `files=` kw.
        create_resp = self.client.post(
            "/api/users/tickets/",
            data={
                "event_id": str(self.event.id),
                "original_price": "100",
                "listing_price": "100",
                "il_legal_declaration": "true",
                "available_quantity": "1",
                "pdf_files_count": "1",
                "delivery_method": "instant",
                "pdf_file_0": pdf,
                "receipt_file": receipt,
            },
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(create_resp.status_code, 201, create_resp.content.decode())
        ticket_id = create_resp.json()["id"]
        t0 = Ticket.objects.get(pk=ticket_id)
        self.assertEqual(t0.status, "pending_approval")

        # --- Admin approves → active (JWT cookies; API has no session auth) ---
        admin_client = Client(enforce_csrf_checks=True)
        csrf = self._csrf_token(admin_client)
        login_adm = admin_client.post(
            "/api/users/login/",
            data=json.dumps(
                {
                    "username": self.admin.username,
                    "password": "AdminPass123!",
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(login_adm.status_code, 200, login_adm.content.decode())
        csrf = self._csrf_token(admin_client)
        appr = admin_client.post(
            f"/api/users/admin/tickets/{ticket_id}/approve/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(appr.status_code, 200, appr.content.decode())
        t0.refresh_from_db()
        self.assertEqual(t0.status, "active")

        # --- Guest client (no seller session) ---
        guest = Client(enforce_csrf_checks=True)
        g_csrf = self._csrf_token(guest)

        pay = guest.post(
            "/api/users/payments/simulate/",
            data=json.dumps(
                {
                    "ticket_id": ticket_id,
                    "amount": 110,
                    "quantity": 1,
                    "timestamp": 1,
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=g_csrf,
        )
        self.assertEqual(pay.status_code, 200, pay.content.decode())
        self.assertTrue(pay.json().get("success"))

        g_csrf = self._csrf_token(guest)
        gc = guest.post(
            "/api/users/orders/guest/",
            data=json.dumps(
                {
                    "guest_email": "guest_overnight_e2e@test.local",
                    "guest_phone": "0501234567",
                    "ticket_id": ticket_id,
                    "total_amount": "110.00",
                    "quantity": 1,
                    "event_name": self.event.name,
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=g_csrf,
        )
        self.assertEqual(gc.status_code, 201, gc.content.decode())
        body = gc.json()
        order_id = body["id"]
        self.assertEqual(body["status"], "pending_payment")
        self.assertTrue(body.get("payment_confirm_token"))

        g_csrf = self._csrf_token(guest)
        cf = guest.post(
            f"/api/users/orders/{order_id}/confirm-payment/",
            data=json.dumps(
                {
                    "mock_payment_ack": True,
                    "guest_email": "guest_overnight_e2e@test.local",
                    "payment_confirm_token": body["payment_confirm_token"],
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=g_csrf,
        )
        self.assertEqual(cf.status_code, 200, cf.content.decode())
        final = cf.json()
        self.assertEqual(final["status"], "paid")

        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.status, "paid")
        self.assertIsNone(order.payment_confirm_token)
        self.assertEqual(order.payout_status, "locked")
        self.assertIsNotNone(order.payout_eligible_date)

        t0.refresh_from_db()
        self.assertEqual(t0.status, "sold")
