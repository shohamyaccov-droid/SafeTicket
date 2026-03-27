"""
QA Marathon: Full offer flow price integrity (Shoham scenario).

Seller lists 100 NIS -> Buyer offers 80 -> Seller accepts -> Buyer checks out.

Asserts Order + serializers + buyer dashboard JSON show:
  final_negotiated_price=80, buyer fee, total_paid_by_buyer=ceil(80*1.10)=88, net_seller_revenue=88.

Run from backend directory (no server required):
    python qa_price_integrity.py

Requires Django settings and DB (SQLite OK).
"""
from __future__ import annotations

import math
import os
import sys
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')

import django

django.setup()

from django.utils import timezone
from django.core.files.base import ContentFile
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import get_user_model
from users.models import Event, Order, Ticket, Offer
from users.serializers import OrderSerializer, ProfileOrderSerializer

User = get_user_model()

LISTING_PRICE = 100
OFFER_BASE = 80
EXPECTED_TOTAL = float(math.ceil(OFFER_BASE * 1.10))  # 88
EXPECTED_FEE = EXPECTED_TOTAL - OFFER_BASE


def _pdf_bytes():
    return b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer<</Size 4/Root 1 0 R>>startxref 178 %%EOF"""


def _jwt_client(user):
    c = APIClient()
    token = RefreshToken.for_user(user)
    c.credentials(HTTP_AUTHORIZATION=f'Bearer {str(token.access_token)}')
    return c


def _host_kw():
    """APIClient uses HTTP_HOST testserver — must match ALLOWED_HOSTS."""
    return {'HTTP_HOST': 'localhost'}


def main() -> int:
    print('=== QA Price Integrity Marathon ===\n')

    ts = timezone.now().strftime('%H%M%S')
    seller = User.objects.create_user(
        username=f'qa_pi_seller_{ts}',
        email=f'qa_pi_seller_{ts}@example.com',
        password='testpass123',
        role='seller',
    )
    buyer = User.objects.create_user(
        username=f'qa_pi_buyer_{ts}',
        email=f'qa_pi_buyer_{ts}@example.com',
        password='testpass123',
        role='buyer',
    )

    event = Event.objects.create(
        name=f'QA Price Integrity {ts}',
        date=timezone.now() + timedelta(days=30),
        venue='מנורה מבטחים',
        city='Tel Aviv',
    )

    ticket = Ticket(
        seller=seller,
        event=event,
        original_price=LISTING_PRICE,
        available_quantity=1,
        status='active',
        delivery_method='instant',
    )
    ticket.pdf_file.save(f'qa_pi_{ts}.pdf', ContentFile(_pdf_bytes()), save=True)

    buyer_cli = _jwt_client(buyer)
    seller_cli = _jwt_client(seller)

    # 1) Offer
    r_offer = buyer_cli.post(
        '/api/users/offers/',
        {'ticket': ticket.id, 'amount': str(OFFER_BASE), 'quantity': 1},
        format='json',
        **_host_kw(),
    )
    assert r_offer.status_code == 201, (r_offer.status_code, r_offer.content)
    offer_id = r_offer.json()['id']

    # 2) Accept
    r_acc = seller_cli.post(f'/api/users/offers/{offer_id}/accept/', format='json', **_host_kw())
    assert r_acc.status_code == 200, (r_acc.status_code, r_acc.content)
    assert r_acc.json().get('status') == 'accepted'

    # 3) Payment simulate (matches CheckoutModal)
    r_pay = buyer_cli.post(
        '/api/users/payments/simulate/',
        {
            'ticket_id': ticket.id,
            'amount': EXPECTED_TOTAL,
            'quantity': 1,
            'offer_id': offer_id,
            'timestamp': int(timezone.now().timestamp() * 1000),
        },
        format='json',
        **_host_kw(),
    )
    assert r_pay.status_code == 200, (r_pay.status_code, r_pay.content)
    assert r_pay.json().get('success') is True

    # 4) Create order
    r_ord = buyer_cli.post(
        '/api/users/orders/',
        {
            'ticket': ticket.id,
            'total_amount': EXPECTED_TOTAL,
            'quantity': 1,
            'event_name': event.name,
            'offer_id': offer_id,
        },
        format='json',
        **_host_kw(),
    )
    assert r_ord.status_code == 201, (r_ord.status_code, r_ord.content)
    body = r_ord.json()

    # 5) Assert API response
    assert abs(float(body['total_amount']) - EXPECTED_TOTAL) < 0.02
    assert abs(float(body['total_paid_by_buyer']) - EXPECTED_TOTAL) < 0.02
    assert abs(float(body['final_negotiated_price']) - OFFER_BASE) < 0.02
    assert abs(float(body['buyer_service_fee']) - EXPECTED_FEE) < 0.02
    assert abs(float(body['net_seller_revenue']) - OFFER_BASE) < 0.02
    assert body.get('related_offer') == offer_id

    order_id = body['id']

    # 6) DB row
    o = Order.objects.get(id=order_id)
    assert abs(float(o.total_amount) - EXPECTED_TOTAL) < 0.02
    assert abs(float(o.total_paid_by_buyer or 0) - EXPECTED_TOTAL) < 0.02
    assert abs(float(o.final_negotiated_price or 0) - OFFER_BASE) < 0.02
    assert o.related_offer_id == offer_id

    # 7) Serializers consistency
    raw = OrderSerializer(o).data
    assert abs(float(raw['total_paid_by_buyer']) - EXPECTED_TOTAL) < 0.02

    prof = ProfileOrderSerializer(o, context={'request': None}).data
    assert abs(float(prof['total_paid_by_buyer']) - EXPECTED_TOTAL) < 0.02
    td = prof.get('ticket_details') or {}
    assert 'original_listing_price' in td
    assert float(td['original_listing_price']) == float(LISTING_PRICE)

    # 8) Buyer dashboard JSON (order history)
    r_dash = buyer_cli.get('/api/users/dashboard/', **_host_kw())
    assert r_dash.status_code == 200
    purchases = r_dash.json().get('purchases') or []
    mine = next((p for p in purchases if p.get('id') == order_id), None)
    assert mine is not None, 'Order missing from dashboard purchases'
    assert abs(float(mine['total_paid_by_buyer']) - EXPECTED_TOTAL) < 0.02
    assert abs(float(mine['total_amount']) - EXPECTED_TOTAL) < 0.02

    print(f'Listing price: {LISTING_PRICE} NIS')
    print(f'Offer (negotiated base): {OFFER_BASE} NIS')
    print(f'Expected buyer total (ceil base×1.10): {EXPECTED_TOTAL} NIS')
    print(f'Order {order_id}: total_paid_by_buyer={mine.get("total_paid_by_buyer")}, fee={mine.get("buyer_service_fee")}')
    print('\nPASS: qa_price_integrity — negotiated price, fee, and totals are consistent across Order, serializers, and dashboard.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
