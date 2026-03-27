"""
SafeTicket pre-launch edge-case QA suite.

Run from backend directory:
    python manage.py test launch_edge_case_qa -v 2

Scenarios:
1. Direct buy vs offer — purchase invalidates pending offers; seller cannot accept after sale.
2. Double accept — two pending offers on one listing; first accept wins; second returns 400.
3. Admin rejection mid-flow — active/reserved ticket rejected; checkout blocked; offers invalidated.
4. Reservation expiry — stale reservation released; sync allows fair checkout (RESERVATION_TIMEOUT_MINUTES).
5. Pairs split — API request for quantity 1 returns 400.
"""

import json
import math
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from rest_framework_simplejwt.tokens import RefreshToken

from users.models import Artist, Event, Offer, Ticket

User = get_user_model()


def _pdf():
    return SimpleUploadedFile(
        "t.pdf",
        b"%PDF-1.4\n1 0 obj<<>>endobj\nxref\n0 1\ntrailer<<>>\n%%EOF",
        content_type="application/pdf",
    )


class LaunchEdgeCaseQATests(TestCase):
    """Multi-user marketplace integrity scenarios."""

    def setUp(self):
        self.seller = User.objects.create_user(
            username="qa_seller",
            email="seller@qa.test",
            password="pass12345",
            role="seller",
        )
        self.buyer_a = User.objects.create_user(
            username="qa_buyer_a",
            email="buyera@qa.test",
            password="pass12345",
            role="buyer",
        )
        self.buyer_b = User.objects.create_user(
            username="qa_buyer_b",
            email="buyerb@qa.test",
            password="pass12345",
            role="buyer",
        )
        self.admin = User.objects.create_superuser(
            username="qa_admin",
            email="admin@qa.test",
            password="pass12345",
        )

        artist = Artist.objects.create(name="QA Artist")
        self.event = Event.objects.create(
            artist=artist,
            name="QA Event",
            date=timezone.now() + timedelta(days=14),
            venue="Venue",
            city="Tel Aviv",
        )

        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=100.00,
            asking_price=100.00,
            pdf_file=_pdf(),
            status="active",
            available_quantity=1,
            verification_status="מאומת",
        )

        self.seller_headers = {
            "HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(self.seller).access_token}"
        }
        self.buyer_a_headers = {
            "HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(self.buyer_a).access_token}"
        }
        self.buyer_b_headers = {
            "HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(self.buyer_b).access_token}"
        }
        self.admin_headers = {
            "HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(self.admin).access_token}"
        }

    def test_direct_buy_invalidates_offer_seller_cannot_accept(self):
        """Buyer B purchases before seller accepts A — A's offer rejected; accept fails."""
        r = self.client.post(
            "/api/users/offers/",
            data=json.dumps({"ticket": self.ticket.id, "amount": "80.00"}),
            content_type="application/json",
            **self.buyer_a_headers,
        )
        self.assertEqual(r.status_code, 201, r.content.decode())
        offer_a_id = r.json()["id"]

        total = math.ceil(float(self.ticket.asking_price) * 1.10)
        pay = self.client.post(
            "/api/users/payments/simulate/",
            {"ticket_id": self.ticket.id, "amount": total, "quantity": 1},
            format="json",
            **self.buyer_b_headers,
        )
        self.assertEqual(pay.status_code, 200, pay.content.decode())

        order = self.client.post(
            "/api/users/orders/",
            {
                "ticket": self.ticket.id,
                "total_amount": total,
                "quantity": 1,
                "event_name": self.event.name,
            },
            format="json",
            **self.buyer_b_headers,
        )
        self.assertEqual(order.status_code, 201, order.content.decode())

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "sold")

        offer_a = Offer.objects.get(id=offer_a_id)
        self.assertEqual(offer_a.status, "rejected")

        acc = self.client.post(
            f"/api/users/offers/{offer_a_id}/accept/",
            data="{}",
            content_type="application/json",
            **self.seller_headers,
        )
        self.assertEqual(acc.status_code, 400, acc.content.decode())
        self.assertIn(b"no longer pending", acc.content.lower())

    def test_double_accept_only_one_succeeds(self):
        """Two pending offers on same ticket — accept first; second returns 400."""
        r1 = self.client.post(
            "/api/users/offers/",
            data=json.dumps({"ticket": self.ticket.id, "amount": "85.00"}),
            content_type="application/json",
            **self.buyer_a_headers,
        )
        r2 = self.client.post(
            "/api/users/offers/",
            data=json.dumps({"ticket": self.ticket.id, "amount": "90.00"}),
            content_type="application/json",
            **self.buyer_b_headers,
        )
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        oid_a = r1.json()["id"]
        oid_b = r2.json()["id"]

        ok = self.client.post(
            f"/api/users/offers/{oid_a}/accept/",
            data="{}",
            content_type="application/json",
            **self.seller_headers,
        )
        self.assertEqual(ok.status_code, 200, ok.content.decode())

        offer_b = Offer.objects.get(id=oid_b)
        self.assertEqual(offer_b.status, "rejected")

        fail = self.client.post(
            f"/api/users/offers/{oid_b}/accept/",
            data="{}",
            content_type="application/json",
            **self.seller_headers,
        )
        self.assertEqual(fail.status_code, 400, fail.content.decode())

    def test_admin_reject_active_blocks_checkout_and_offers(self):
        """Admin rejects an active listing — order blocked; pending offers rejected."""
        r = self.client.post(
            "/api/users/offers/",
            data=json.dumps({"ticket": self.ticket.id, "amount": "88.00"}),
            content_type="application/json",
            **self.buyer_a_headers,
        )
        self.assertEqual(r.status_code, 201)
        offer_id = r.json()["id"]

        rej = self.client.post(
            f"/api/users/admin/tickets/{self.ticket.id}/reject/",
            data="{}",
            content_type="application/json",
            **self.admin_headers,
        )
        self.assertEqual(rej.status_code, 200, rej.content.decode())

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "rejected")

        offer = Offer.objects.get(id=offer_id)
        self.assertEqual(offer.status, "rejected")

        total = math.ceil(float(self.ticket.asking_price) * 1.10)
        self.client.post(
            "/api/users/payments/simulate/",
            {"ticket_id": self.ticket.id, "amount": total, "quantity": 1},
            format="json",
            **self.buyer_b_headers,
        )
        order = self.client.post(
            "/api/users/orders/",
            {
                "ticket": self.ticket.id,
                "total_amount": total,
                "quantity": 1,
                "event_name": self.event.name,
            },
            format="json",
            **self.buyer_b_headers,
        )
        self.assertEqual(order.status_code, 400, order.content.decode())

    def test_reservation_expires_releases_listing(self):
        """Expired reservation is released; abandoned-cart cleanup + checkout rules apply."""
        self.client.post(
            f"/api/users/tickets/{self.ticket.id}/reserve/",
            data=json.dumps({}),
            content_type="application/json",
            **self.buyer_a_headers,
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "reserved")

        old = timezone.now() - timedelta(minutes=30)
        Ticket.objects.filter(id=self.ticket.id).update(reserved_at=old)

        from users.views import release_abandoned_carts

        release_abandoned_carts()

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "active")
        self.assertIsNone(self.ticket.reserved_by_id)

        total = math.ceil(float(self.ticket.asking_price) * 1.10)
        self.client.post(
            "/api/users/payments/simulate/",
            {"ticket_id": self.ticket.id, "amount": total, "quantity": 1},
            format="json",
            **self.buyer_b_headers,
        )
        order = self.client.post(
            "/api/users/orders/",
            {
                "ticket": self.ticket.id,
                "total_amount": total,
                "quantity": 1,
                "event_name": self.event.name,
            },
            format="json",
            **self.buyer_b_headers,
        )
        self.assertEqual(order.status_code, 201, order.content.decode())

    def test_pairs_split_quantity_one_returns_400(self):
        """Pairs-only listing — create_order with quantity 1 must fail."""
        self.ticket.split_type = "זוגות בלבד"
        self.ticket.available_quantity = 2
        self.ticket.save()

        total = math.ceil(float(self.ticket.asking_price) * 1.10) * 1
        self.client.post(
            "/api/users/payments/simulate/",
            {"ticket_id": self.ticket.id, "amount": total, "quantity": 1},
            format="json",
            **self.buyer_b_headers,
        )
        order = self.client.post(
            "/api/users/orders/",
            {
                "ticket": self.ticket.id,
                "total_amount": total,
                "quantity": 1,
                "event_name": self.event.name,
            },
            format="json",
            **self.buyer_b_headers,
        )
        self.assertEqual(order.status_code, 400, order.content.decode())
        self.assertIn(b"pairs", order.content.lower())

    def test_reserved_by_other_buyer_blocks_purchase(self):
        """Active reservation by another user blocks create_order."""
        self.client.post(
            f"/api/users/tickets/{self.ticket.id}/reserve/",
            data=json.dumps({}),
            content_type="application/json",
            **self.buyer_a_headers,
        )
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "reserved")

        total = math.ceil(float(self.ticket.asking_price) * 1.10)
        self.client.post(
            "/api/users/payments/simulate/",
            {"ticket_id": self.ticket.id, "amount": total, "quantity": 1},
            format="json",
            **self.buyer_b_headers,
        )
        order = self.client.post(
            "/api/users/orders/",
            {
                "ticket": self.ticket.id,
                "total_amount": total,
                "quantity": 1,
                "event_name": self.event.name,
            },
            format="json",
            **self.buyer_b_headers,
        )
        self.assertEqual(order.status_code, 400, order.content.decode())
        self.assertIn(b"reserved", order.content.lower())
