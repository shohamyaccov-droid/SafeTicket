"""
Autonomous marathon QA: sequential double-purchase on one ticket (inventory guard)
and guest checkout happy path. Simulates race outcome without threaded Django clients.

Run: python manage.py test test_autonomous_marathon_qa -v 2
"""

import json
from decimal import Decimal

from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from django.contrib.auth import get_user_model

from users.models import Ticket, Event, Order

User = get_user_model()


def _minimal_pdf():
    return ContentFile(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n", "marathon.pdf")


class GuestCheckoutConcurrencyQATest(TestCase):
    """Second guest checkout on the same single-ticket listing must fail after first sale."""

    def setUp(self):
        self.seller = User.objects.create_user(
            username="marathon_seller_qa",
            email="marathon_seller_qa@test.local",
            password="TestPass123!",
        )
        future = timezone.now() + timedelta(days=30)
        self.event = Event.objects.create(
            name="Marathon QA Event",
            date=future,
            venue="מנורה מבטחים",
            city="תל אביב",
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal("100.00"),
            status="active",
            available_quantity=1,
            pdf_file=_minimal_pdf(),
            verification_status="מאומת",
        )

    def _csrf_post_guest(self, client, payload):
        r0 = client.get("/api/users/csrf/")
        self.assertEqual(r0.status_code, 200)
        token = r0.cookies.get("csrftoken")
        self.assertIsNotNone(token)
        return client.post(
            "/api/users/orders/guest/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token.value,
        )

    def _csrf_confirm_guest(self, client, order_id, guest_email):
        r0 = client.get("/api/users/csrf/")
        self.assertEqual(r0.status_code, 200)
        token = r0.cookies.get("csrftoken")
        self.assertIsNotNone(token)
        return client.post(
            f"/api/users/orders/{order_id}/confirm-payment/",
            data=json.dumps(
                {"mock_payment_ack": True, "guest_email": guest_email}
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token.value,
        )

    def test_second_guest_checkout_fails_after_ticket_sold(self):
        client = self.client
        base_payload = {
            "guest_email": "guest_a@marathon.test",
            "guest_phone": "0500000001",
            "ticket_id": self.ticket.id,
            "total_amount": "110.00",
            "quantity": 1,
            "event_name": self.event.name,
        }
        r1 = self._csrf_post_guest(client, base_payload)
        self.assertEqual(r1.status_code, 201, r1.content.decode())
        oid = r1.json().get("id")
        c1 = self._csrf_confirm_guest(client, oid, base_payload["guest_email"])
        self.assertEqual(c1.status_code, 200, c1.content.decode())

        r2 = self._csrf_post_guest(
            client,
            {
                **base_payload,
                "guest_email": "guest_b@marathon.test",
                "guest_phone": "0500000002",
            },
        )
        self.assertEqual(r2.status_code, 400)
        body = r2.json()
        err = (body.get("error") or "").lower()
        self.assertTrue(
            "available" in err
            or "longer" in err
            or "sold" in err
            or "reserved" in err,
            msg=body,
        )
        self.assertEqual(Order.objects.filter(ticket_id=self.ticket.id).count(), 1)

    def test_first_guest_checkout_succeeds_and_marks_ticket_sold(self):
        client = self.client
        r = self._csrf_post_guest(
            client,
            {
                "guest_email": "guest_ok@marathon.test",
                "guest_phone": "0500000003",
                "ticket_id": self.ticket.id,
                "total_amount": "110.00",
                "quantity": 1,
                "event_name": self.event.name,
            },
        )
        self.assertEqual(r.status_code, 201, r.content.decode())
        oid = r.json().get("id")
        c = self._csrf_confirm_guest(client, oid, "guest_ok@marathon.test")
        self.assertEqual(c.status_code, 200, c.content.decode())
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "sold")
        self.assertEqual(self.ticket.available_quantity, 0)
