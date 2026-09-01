"""
High-level Integration / E2E suite for the Offer mechanism.

Run with:
  python manage.py test offers.tests -v 2
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Offer, Order, Ticket
from users.pricing import expected_buy_now_total, expected_negotiated_total_from_offer_base
from users.views import (
    HE_OFFER_ALREADY_CONSUMED,
    HE_TICKET_ALREADY_SOLD,
    RESERVATION_TIMEOUT_MINUTES,
    release_abandoned_carts,
)

User = get_user_model()


def _pdf():
    return SimpleUploadedFile(
        'e2e_ticket.pdf',
        b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF',
        content_type='application/pdf',
    )


def _make_users(prefix: str):
    seller = User.objects.create_user(
        username=f'{prefix}_seller',
        email=f'{prefix}_seller@e2e.test',
        password='Pass12345!',
        role='seller',
    )
    buyer1 = User.objects.create_user(
        username=f'{prefix}_buyer1',
        email=f'{prefix}_buyer1@e2e.test',
        password='Pass12345!',
        role='buyer',
    )
    buyer2 = User.objects.create_user(
        username=f'{prefix}_buyer2',
        email=f'{prefix}_buyer2@e2e.test',
        password='Pass12345!',
        role='buyer',
    )
    return seller, buyer1, buyer2


def _make_ticket(seller, *, name_suffix: str, asking: str = '200.00'):
    artist = Artist.objects.create(name=f'E2E Artist {name_suffix}')
    event = Event.objects.create(
        artist=artist,
        name=f'E2E Event {name_suffix}',
        date=timezone.now() + timedelta(days=30),
        venue='Arena',
        city='Tel Aviv',
        country='IL',
        category='concert',
        status='פעיל',
    )
    return Ticket.objects.create(
        seller=seller,
        event=event,
        event_name=event.name,
        original_price=Decimal(asking),
        asking_price=Decimal(asking),
        pdf_file=_pdf(),
        status='active',
        verification_status='מאומת',
        available_quantity=1,
        delivery_method='instant',
    )


def _auth_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _create_and_accept_offer(*, buyer, seller, ticket, amount: str):
    buyer_client = _auth_client(buyer)
    create_resp = buyer_client.post(
        '/api/users/offers/',
        {
            'ticket': ticket.id,
            'amount': amount,
            'quantity': 1,
        },
        format='json',
    )
    assert create_resp.status_code in (200, 201), create_resp.data
    offer_id = create_resp.data['id']

    seller_client = _auth_client(seller)
    accept_resp = seller_client.post(f'/api/users/offers/{offer_id}/accept/', {}, format='json')
    assert accept_resp.status_code == 200, accept_resp.data
    return Offer.objects.get(pk=offer_id)


def _checkout_offer(*, buyer, ticket, offer):
    client = _auth_client(buyer)
    total = expected_negotiated_total_from_offer_base(offer.amount)
    create_resp = client.post(
        '/api/users/orders/',
        {
            'ticket': ticket.id,
            'quantity': 1,
            'offer_id': offer.id,
            'total_amount': str(total),
            'accepted_terms': True,
        },
        format='json',
    )
    return client, create_resp


def _confirm_payment(client: APIClient, order_id: int, token):
    payload = {'mock_payment_ack': True}
    if token:
        payload['payment_confirm_token'] = token
    return client.post(
        f'/api/users/orders/{order_id}/confirm-payment/',
        payload,
        format='json',
    )


@override_settings(
    REST_FRAMEWORK={
        **settings.REST_FRAMEWORK,
        'DEFAULT_THROTTLE_RATES': {
            **settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}),
            'offers': '100000/minute',
            'offers_mutations': '100000/minute',
            'checkout': '100000/minute',
            'checkout_reserve': '100000/minute',
        },
    }
)
class OfferMechanismE2ETests(TransactionTestCase):
    """Offer-flow scenarios (seller + buyer at API/DB level).

    Uses TransactionTestCase so concurrent reservation / sale paths see committed rows.
    """

    # ------------------------------------------------------------------
    # SCENARIO 2 — Multi-buyer accepted race (fast path first)
    # ------------------------------------------------------------------
    def test_scenario_2_multi_buyer_accepted_race_winner_completes(self):
        seller, buyer1, buyer2 = _make_users('s2')
        ticket = _make_ticket(seller, name_suffix='s2-race', asking='250.00')

        c1 = _auth_client(buyer1)
        r1 = c1.post(
            '/api/users/offers/',
            {'ticket': ticket.id, 'amount': '220.00', 'quantity': 1},
            format='json',
        )
        self.assertIn(r1.status_code, (200, 201), r1.data)
        offer_a = Offer.objects.get(pk=r1.data['id'])

        c2 = _auth_client(buyer2)
        r2 = c2.post(
            '/api/users/offers/',
            {'ticket': ticket.id, 'amount': '230.00', 'quantity': 1},
            format='json',
        )
        self.assertIn(r2.status_code, (200, 201), r2.data)
        offer_b = Offer.objects.get(pk=r2.data['id'])

        seller_client = _auth_client(seller)
        acc_a = seller_client.post(f'/api/users/offers/{offer_a.id}/accept/', {}, format='json')
        self.assertEqual(acc_a.status_code, 200, acc_a.data)

        offer_a.refresh_from_db()
        offer_b.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(offer_a.status, 'accepted')
        # Accepted offer must NOT hide inventory from the marketplace.
        self.assertEqual(ticket.status, 'active')
        self.assertIsNone(ticket.reserved_by_id)

        # Residual dual-accept race: resurrect Offer B as accepted while listing stays active.
        now = timezone.now()
        Offer.objects.filter(pk=offer_b.pk).update(
            status='accepted',
            accepted_at=now,
            checkout_expires_at=now + timedelta(hours=24),
        )
        offer_b.refresh_from_db()
        self.assertEqual(offer_b.status, 'accepted')
        self.assertEqual(
            Offer.objects.filter(ticket=ticket, status='accepted').count(),
            2,
            'Precondition: both offers accepted (multi-buyer lock state)',
        )

        client1, create_resp = _checkout_offer(buyer=buyer1, ticket=ticket, offer=offer_a)
        self.assertEqual(create_resp.status_code, 201, create_resp.data)
        order_id = create_resp.data['id']
        token = create_resp.data.get('payment_confirm_token')
        pay_resp = _confirm_payment(client1, order_id, token)
        self.assertIn(pay_resp.status_code, (200, 201), getattr(pay_resp, 'data', pay_resp))

        ticket.refresh_from_db()
        offer_a.refresh_from_db()
        offer_b.refresh_from_db()
        order = Order.objects.get(pk=order_id)

        self.assertEqual(ticket.status, 'sold')
        self.assertEqual(order.status, 'paid')
        self.assertEqual(offer_a.status, 'completed', 'Winning offer must be consumed')
        self.assertIn(
            offer_b.status,
            ('rejected', 'expired'),
            f'Losing offer must be invalidated, got {offer_b.status}',
        )

        _client2, lose_resp = _checkout_offer(buyer=buyer2, ticket=ticket, offer=offer_b)
        self.assertEqual(lose_resp.status_code, 400, lose_resp.data)
        err = str(lose_resp.data.get('error') or lose_resp.data)
        self.assertTrue(
            HE_TICKET_ALREADY_SOLD in err
            or 'already sold' in err.lower()
            or 'sold' in err.lower()
            or HE_OFFER_ALREADY_CONSUMED in err
            or 'consumed' in err.lower()
            or 'ineligible' in err.lower(),
            f'Expected sold/invalidated error, got: {err}',
        )

    # ------------------------------------------------------------------
    # SCENARIO 3 — Accepted offer re-use (double checkout)
    # ------------------------------------------------------------------
    def test_scenario_3_offer_reuse_blocked_after_successful_checkout(self):
        seller, buyer1, _ = _make_users('s3')
        ticket = _make_ticket(seller, name_suffix='s3-reuse')
        offer = _create_and_accept_offer(
            buyer=buyer1, seller=seller, ticket=ticket, amount='175.00'
        )

        client, create_resp = _checkout_offer(buyer=buyer1, ticket=ticket, offer=offer)
        self.assertEqual(create_resp.status_code, 201, create_resp.data)
        order_id = create_resp.data['id']
        token = create_resp.data.get('payment_confirm_token')
        pay_resp = _confirm_payment(client, order_id, token)
        self.assertIn(pay_resp.status_code, (200, 201), getattr(pay_resp, 'data', pay_resp))

        offer.refresh_from_db()
        self.assertEqual(offer.status, 'completed')

        _client2, reuse_resp = _checkout_offer(buyer=buyer1, ticket=ticket, offer=offer)
        self.assertEqual(reuse_resp.status_code, 400, reuse_resp.data)
        err = str(reuse_resp.data.get('error') or reuse_resp.data)
        self.assertIn(
            HE_OFFER_ALREADY_CONSUMED,
            err,
            f'Expected explicit "{HE_OFFER_ALREADY_CONSUMED}" error, got: {err}',
        )

    # ------------------------------------------------------------------
    # SCENARIO 4 — Unauthenticated offer probing
    # ------------------------------------------------------------------
    def test_scenario_4_unauthenticated_offer_probing_forbidden(self):
        seller, buyer1, buyer2 = _make_users('s4')
        ticket = _make_ticket(seller, name_suffix='s4-probe')

        offer_ids = []
        for buyer, amount in ((buyer1, '150.00'), (buyer2, '160.00'), (buyer1, '155.00')):
            if offer_ids:
                ticket = _make_ticket(seller, name_suffix=f's4-probe-{len(offer_ids)}')
            c = _auth_client(buyer)
            resp = c.post(
                '/api/users/offers/',
                {'ticket': ticket.id, 'amount': amount, 'quantity': 1},
                format='json',
            )
            self.assertIn(resp.status_code, (200, 201), resp.data)
            offer_ids.append(resp.data['id'])

        self.assertGreaterEqual(len(offer_ids), 3)

        guest = Client()
        for oid in offer_ids:
            path = f'/api/users/offers/{oid}/'
            resp = guest.get(path)
            self.assertIn(
                resp.status_code,
                (401, 403),
                f'Anonymous GET {path} must be 401/403, got {resp.status_code}: {resp.content[:200]}',
            )

        for path in ('/api/users/offers/', '/api/users/offers/sent/', '/api/users/offers/received/'):
            resp = guest.get(path)
            self.assertIn(
                resp.status_code,
                (401, 403),
                f'Anonymous GET {path} must be 401/403, got {resp.status_code}',
            )

        connection.ensure_connection()
        self.assertTrue(Offer.objects.filter(pk__in=offer_ids).exists())

    # ------------------------------------------------------------------
    # SCENARIO 1 — Accept leaves listing visible; cart TTL (not 24h) owns lock
    # ------------------------------------------------------------------
    def test_scenario_z1_accept_keeps_ticket_active_and_cart_ttl_releases(self):
        seller, buyer1, buyer2 = _make_users('s1')
        ticket = _make_ticket(seller, name_suffix='s1-hold')
        offer = _create_and_accept_offer(
            buyer=buyer1, seller=seller, ticket=ticket, amount='180.00'
        )

        ticket.refresh_from_db()
        self.assertEqual(offer.status, 'accepted')
        self.assertEqual(ticket.status, 'active', 'Accepted offer must not hide marketplace listing')
        self.assertIsNone(ticket.reserved_by_id)
        self.assertIsNotNone(offer.checkout_expires_at)
        self.assertGreater(offer.checkout_expires_at, timezone.now() + timedelta(hours=20))

        # Proceed-to-Payment style lock: reserve via API (10-minute cart hold)
        client1 = _auth_client(buyer1)
        reserve_resp = client1.post(f'/api/users/tickets/{ticket.id}/reserve/', {}, format='json')
        self.assertEqual(reserve_resp.status_code, 200, reserve_resp.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')
        self.assertEqual(ticket.reserved_by_id, buyer1.id)

        # Backdate reservation past cart TTL — sweeper must release (offer stays accepted)
        Ticket.objects.filter(pk=ticket.pk).update(
            reserved_at=timezone.now() - timedelta(minutes=RESERVATION_TIMEOUT_MINUTES + 2),
            locked_until=timezone.now() - timedelta(seconds=1),
        )
        released = release_abandoned_carts()
        self.assertGreaterEqual(int(released or 0), 1)
        ticket.refresh_from_db()
        offer.refresh_from_db()
        self.assertEqual(ticket.status, 'active')
        self.assertIsNone(ticket.reserved_by_id)
        self.assertEqual(offer.status, 'accepted', '24h offer window survives cart release')

        # Buyer 2 can buy at full price while Buyer 1 still has an accepted offer
        client2 = _auth_client(buyer2)
        buy_now_total = expected_buy_now_total(ticket.asking_price, 1)
        create_resp = client2.post(
            '/api/users/orders/',
            {
                'ticket': ticket.id,
                'quantity': 1,
                'total_amount': str(buy_now_total),
                'accepted_terms': True,
            },
            format='json',
        )
        self.assertEqual(create_resp.status_code, 201, create_resp.data)
        order_id = create_resp.data['id']
        token = create_resp.data.get('payment_confirm_token')
        pay_resp = _confirm_payment(client2, order_id, token)
        self.assertIn(pay_resp.status_code, (200, 201), getattr(pay_resp, 'data', pay_resp))

        ticket.refresh_from_db()
        offer.refresh_from_db()
        self.assertEqual(ticket.status, 'sold')
        self.assertIn(
            offer.status,
            ('rejected', 'expired'),
            f'Losing negotiated offer must be invalidated, got {offer.status}',
        )

        _client, lose_resp = _checkout_offer(buyer=buyer1, ticket=ticket, offer=offer)
        self.assertEqual(lose_resp.status_code, 400, lose_resp.data)
        err = str(lose_resp.data.get('error') or lose_resp.data)
        self.assertTrue(
            HE_TICKET_ALREADY_SOLD in err
            or 'already sold' in err.lower()
            or 'sold' in err.lower()
            or 'ineligible' in err.lower(),
            f'Expected sold/invalidated error, got: {err}',
        )
