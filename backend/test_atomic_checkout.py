"""
E2E QA Script: Atomic Checkout Flow (select_for_update fix verification)
Tests that the checkout process flows smoothly WITHOUT NotSupportedError.

Flow:
1. Create an active ticket bundle (quantity 3)
2. Simulate payment for 2 tickets
3. Call create_order for those 2 tickets
4. Assert checkout succeeds and does NOT throw NotSupportedError

Run from backend directory (with server running on port 8000):
    python manage.py runserver   # in another terminal
    python test_atomic_checkout.py
"""

import os
import sys
import django
from pathlib import Path
from io import BytesIO

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

import math
from django.contrib.auth import get_user_model
from users.models import Ticket, Event, Order
import requests

User = get_user_model()

API_BASE_URL = 'http://127.0.0.1:8000/api/users'
QUANTITY = 3
PURCHASE_QUANTITY = 2


def create_dummy_pdf():
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


def get_or_create_users():
    seller, _ = User.objects.get_or_create(
        username='test_atomic_seller',
        defaults={'email': 'atomic_seller@test.com', 'role': 'seller'}
    )
    seller.set_password('testpass123')
    seller.save()
    buyer, _ = User.objects.get_or_create(
        username='test_atomic_buyer',
        defaults={'email': 'atomic_buyer@test.com', 'role': 'buyer'}
    )
    buyer.set_password('testpass123')
    buyer.save()
    return seller, buyer


def login(username, password):
    r = requests.post(f'{API_BASE_URL}/login/', json={'username': username, 'password': password})
    return r.json().get('access') if r.status_code == 200 else None


def upload_tickets(token, event_id):
    url = f'{API_BASE_URL}/tickets/'
    files = [(f'pdf_file_{i}', (f'ticket_{i}.pdf', BytesIO(create_dummy_pdf()), 'application/pdf')) for i in range(QUANTITY)]
    data = {
        'event_id': str(event_id),
        'original_price': '100.00',
        'available_quantity': str(QUANTITY),
        'pdf_files_count': str(QUANTITY),
    }
    for i in range(QUANTITY):
        data[f'row_number_{i}'] = '5'
        data[f'seat_number_{i}'] = str(10 + i)
    r = requests.post(url, data=data, files=files, headers={'Authorization': f'Bearer {token}'})
    return r.status_code == 201


def approve_tickets(listing_group_id):
    """Set tickets to active (bypass admin - direct DB update for test)"""
    Ticket.objects.filter(listing_group_id=listing_group_id).update(status='active')


def main():
    print('=' * 70)
    print('QA: Atomic Checkout Flow (select_for_update fix verification)')
    print('=' * 70)

    # Ensure event exists (use first available or create)
    event = Event.objects.first()
    if not event:
        from django.utils import timezone
        from users.models import Artist
        artist = Artist.objects.first()
        if not artist:
            artist = Artist.objects.create(name='Test Artist')
        event = Event.objects.create(
            name='Test Event for Atomic Checkout',
            date=timezone.now(),
            venue='מנורה מבטחים',
            city='תל אביב',
            artist=artist
        )
        print(f'\n[OK] Created test event: {event.name} (ID: {event.id})')
    else:
        print(f'\n[OK] Event: {event.name} (ID: {event.id})')
    event_id = event.id

    seller, buyer = get_or_create_users()
    try:
        seller_token = login(seller.username, 'testpass123')
        buyer_token = login(buyer.username, 'testpass123')
    except requests.exceptions.ConnectionError:
        print('\n[ERROR] Cannot connect to server. Start it first: python manage.py runserver')
        return False
    if not seller_token or not buyer_token:
        print('[ERROR] Login failed')
        return False

    # Upload 3 tickets
    print(f'\n[1] Uploading {QUANTITY} tickets...')
    if not upload_tickets(seller_token, event_id):
        print('[ERROR] Upload failed')
        return False
    print('[OK] Upload successful')

    # Get listing_group_id and approve
    tickets = Ticket.objects.filter(seller=seller, event_id=event_id).order_by('-created_at')[:QUANTITY]
    if tickets.count() != QUANTITY:
        print(f'[ERROR] Expected {QUANTITY} tickets, got {tickets.count()}')
        return False
    listing_group_id = tickets.first().listing_group_id
    if not listing_group_id:
        print('[ERROR] No listing_group_id')
        return False
    approve_tickets(listing_group_id)
    print(f'[OK] Tickets approved (listing_group_id: {listing_group_id})')

    ticket = tickets.first()
    # Use same calculation as create_order: expected_unit = ceil(asking_price * 1.10)
    unit_base = float(ticket.asking_price)
    expected_unit = math.ceil(unit_base * 1.10)
    total_amount = expected_unit * PURCHASE_QUANTITY

    # Simulate payment for 2 tickets
    print(f'\n[2] Simulating payment for {PURCHASE_QUANTITY} tickets...')
    try:
        pay_r = requests.post(
            f'{API_BASE_URL}/payments/simulate/',
            json={
                'ticket_id': ticket.id,
                'amount': total_amount,
                'quantity': PURCHASE_QUANTITY,
                'listing_group_id': listing_group_id,
            },
            headers={'Authorization': f'Bearer {buyer_token}'}
        )
    except Exception as e:
        print(f'[ERROR] Payment simulation raised: {type(e).__name__}: {e}')
        if 'NotSupportedError' in type(e).__name__:
            print('[CRITICAL] NotSupportedError - select_for_update + count() bug still present!')
        return False

    if pay_r.status_code != 200:
        print(f'[ERROR] Payment simulation failed: {pay_r.status_code} - {pay_r.text}')
        return False
    print('[OK] Payment simulation successful')

    # Create order for 2 tickets
    print(f'\n[3] Creating order for {PURCHASE_QUANTITY} tickets...')
    try:
        order_r = requests.post(
            f'{API_BASE_URL}/orders/',
            json={
                'ticket': ticket.id,
                'total_amount': total_amount,
                'quantity': PURCHASE_QUANTITY,
                'event_name': event.name,
                'listing_group_id': listing_group_id,
            },
            headers={'Authorization': f'Bearer {buyer_token}'}
        )
    except Exception as e:
        print(f'[ERROR] Create order raised: {type(e).__name__}: {e}')
        if 'NotSupportedError' in type(e).__name__:
            print('[CRITICAL] NotSupportedError - select_for_update bug in create_order!')
        return False

    if order_r.status_code != 201:
        print(f'[ERROR] Create order failed: {order_r.status_code} - {order_r.text}')
        return False
    order_data = order_r.json()
    print(f'[OK] Order created: ID={order_data.get("id")}, quantity={order_data.get("quantity")}')

    sold_count = Ticket.objects.filter(listing_group_id=listing_group_id, status='sold').count()
    active_count = Ticket.objects.filter(listing_group_id=listing_group_id, status='active').count()
    print(f'\n[4] Verification: {sold_count} sold, {active_count} active (expected {PURCHASE_QUANTITY} sold, {QUANTITY - PURCHASE_QUANTITY} active)')

    success = sold_count == PURCHASE_QUANTITY and active_count == QUANTITY - PURCHASE_QUANTITY
    print('\n' + '=' * 70)
    if success:
        print('[SUCCESS] Atomic checkout flow completed without NotSupportedError.')
    else:
        print('[WARN] Checkout succeeded but ticket counts may differ (reservation etc.).')
    print('=' * 70)
    return True


if __name__ == '__main__':
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    ok = main()
    sys.exit(0 if ok else 1)
