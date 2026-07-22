"""
High-level Integration / E2E suite for the Offer mechanism.

Run with:
  python manage.py test offers.tests -v 2

Scenario 1 physically sleeps ~11 minutes to prove the 24h offer hold is not
swept by the 10-minute abandoned-cart reservation sweeper.
"""
from __future__ import annotations

import threading
import time
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Offer, Order, Ticket
from users.pricing import expected_negotiated_total_from_offer_base
from users.views import (
    HE_OFFER_ALREADY_CONSUMED,
    HE_TICKET_ALREADY_SOLD,
    release_abandoned_carts,
)

User = get_user_model()

# Physical wait: 11 minutes + 1 second (Scenario 1).
OFFER_HOLD_VS_SWEEPER_SLEEP_SECONDS = (11 * 60) + 1


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
    """Four autonomous offer-flow scenarios (seller + buyer at API/DB level).

    Uses TransactionTestCase so Scenario 1's background sweeper thread can see
    committed inventory / offer rows (plain TestCase wraps in an unshared txn).
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
        self.assertEqual(ticket.status, 'reserved')
        self.assertEqual(ticket.reserved_by_id, buyer1.id)

        # Residual dual-accept race: resurrect Offer B as accepted while inventory held.
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
    # SCENARIO 1 — 11-minute race: offer hold vs 10-minute sweeper
    # (Runs last so faster scenarios fail-fast before the long sleep.)
    # ------------------------------------------------------------------
    def test_scenario_z1_eleven_minute_hold_survives_reservation_sweeper(self):
        seller, buyer1, _ = _make_users('s1')
        ticket = _make_ticket(seller, name_suffix='s1-hold')
        offer = _create_and_accept_offer(
            buyer=buyer1, seller=seller, ticket=ticket, amount='180.00'
        )

        ticket.refresh_from_db()
        self.assertEqual(offer.status, 'accepted')
        self.assertEqual(ticket.status, 'reserved')
        self.assertEqual(ticket.reserved_by_id, buyer1.id)
        self.assertIsNotNone(offer.checkout_expires_at)
        self.assertGreater(offer.checkout_expires_at, timezone.now() + timedelta(hours=20))

        offer_id = offer.id
        ticket_id = ticket.id
        buyer1_id = buyer1.id

        stop_event = threading.Event()
        sweep_counts = []
        integrity_ok = {'value': True, 'notes': []}

        def sweeper_loop():
            """While the hold sleeps, hammer the 10-minute reservation sweeper."""
            close_old_connections()
            while not stop_event.wait(30):
                try:
                    close_old_connections()
                    released = release_abandoned_carts()
                    sweep_counts.append(int(released or 0))
                    live_offer = Offer.objects.get(pk=offer_id)
                    live_ticket = Ticket.objects.get(pk=ticket_id)
                    if live_offer.status != 'accepted':
                        integrity_ok['value'] = False
                        integrity_ok['notes'].append(f'offer drifted to {live_offer.status}')
                    if live_ticket.status != 'reserved' or live_ticket.reserved_by_id != buyer1_id:
                        integrity_ok['value'] = False
                        integrity_ok['notes'].append(
                            f'ticket drifted status={live_ticket.status} '
                            f'reserved_by={live_ticket.reserved_by_id}'
                        )
                    if live_ticket.status == 'sold' and not Order.objects.filter(
                        ticket_id=ticket_id
                    ).exists():
                        integrity_ok['value'] = False
                        integrity_ok['notes'].append('ticket sold without order')
                except Exception as exc:  # pragma: no cover
                    integrity_ok['value'] = False
                    integrity_ok['notes'].append(f'sweeper thread error: {exc}')
                finally:
                    close_old_connections()

        worker = threading.Thread(target=sweeper_loop, name='offer-hold-sweeper', daemon=True)
        worker.start()
        try:
            # Physical wait — do not mock time. Per product requirement.
            time.sleep(OFFER_HOLD_VS_SWEEPER_SLEEP_SECONDS)
            release_abandoned_carts()
            release_abandoned_carts()
        finally:
            stop_event.set()
            worker.join(timeout=60)

        offer.refresh_from_db()
        ticket.refresh_from_db()

        self.assertTrue(
            integrity_ok['value'],
            f'Integrity checks failed during sleep: {integrity_ok["notes"]}',
        )
        self.assertEqual(offer.status, 'accepted', 'Accepted offer must remain valid after 11m+')
        self.assertEqual(ticket.status, 'reserved', 'Ticket must stay locked for Buyer 1')
        self.assertEqual(ticket.reserved_by_id, buyer1.id)
        self.assertIsNotNone(ticket.reserved_at)
        self.assertGreaterEqual(len(sweep_counts), 1)

        _client, create_resp = _checkout_offer(buyer=buyer1, ticket=ticket, offer=offer)
        self.assertEqual(create_resp.status_code, 201, create_resp.data)
