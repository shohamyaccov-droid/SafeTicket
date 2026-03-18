"""
E2E QA Simulation: Multi-Ticket Download Flow
Proves that a buyer can download ALL tickets after purchasing a bundle.

Flow:
1. Create 4 tickets in a listing group (with PDFs)
2. Create order for quantity=4 via listing_group_id
3. Fetch order details (from create_order response)
4. Assert: order has tickets array with exactly 4 distinct tickets and 4 distinct pdf_file URLs

Run from backend directory:
    python test_multi_ticket_download.py

Requires: Server running (python manage.py runserver)
"""

import os
import sys
import django
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from django.contrib.auth import get_user_model
from users.models import Ticket, Event, Order
import requests

User = get_user_model()

API_BASE_URL = 'http://127.0.0.1:8000/api/users'
EVENT_ID = 2  # Adjust if your test event differs


def create_dummy_pdf():
    """Create a minimal valid PDF"""
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
178
%%EOF"""


def get_auth_token(username, password):
    url = f"{API_BASE_URL}/login/"
    response = requests.post(url, json={'username': username, 'password': password})
    if response.status_code == 200:
        return response.json().get('access')
    return None


def create_test_users():
    seller, _ = User.objects.get_or_create(
        username='test_seller_multi',
        defaults={'email': 'seller_multi@test.com', 'password': 'testpass123'}
    )
    if not seller.has_usable_password():
        seller.set_password('testpass123')
        seller.save()

    buyer, _ = User.objects.get_or_create(
        username='test_buyer_multi',
        defaults={'email': 'buyer_multi@test.com', 'password': 'testpass123'}
    )
    if not buyer.has_usable_password():
        buyer.set_password('testpass123')
        buyer.save()

    return seller, buyer


def upload_tickets(seller_token, event_id, quantity=4):
    """Upload tickets with PDFs in one request - they get same listing_group_id"""
    url = f"{API_BASE_URL}/tickets/"
    headers = {'Authorization': f'Bearer {seller_token}'}
    data = {
        'event_id': str(event_id),
        'original_price': '100.00',
        'available_quantity': str(quantity),
        'is_together': 'true',
        'pdf_files_count': str(quantity),
    }
    for i in range(quantity):
        data[f'row_number_{i}'] = '5'
        data[f'seat_number_{i}'] = str(i + 1)
    files = []
    for i in range(quantity):
        pdf_file = create_dummy_pdf()
        files.append((f'pdf_file_{i}', (f'ticket_{i}.pdf', pdf_file, 'application/pdf')))
    response = requests.post(url, data=data, files=files, headers=headers)
    if response.status_code != 201:
        print(f"  ✗ Upload failed: {response.status_code} - {response.text[:300]}")
        return []
    first_ticket = response.json()
    listing_group_id = first_ticket.get('listing_group_id')
    if not listing_group_id:
        print("  ✗ No listing_group_id in response - fetch from DB")
        db_tickets = list(Ticket.objects.filter(event_id=event_id).order_by('-id')[:quantity])
        if db_tickets:
            listing_group_id = db_tickets[0].listing_group_id
            tickets = [{'id': t.id, 'listing_group_id': t.listing_group_id} for t in db_tickets]
        else:
            return []
    else:
        tickets = list(Ticket.objects.filter(listing_group_id=listing_group_id).order_by('id').values('id', 'listing_group_id'))
    for i, t in enumerate(tickets):
        print(f"  ✓ Ticket {i+1}: ID {t['id']}")
    return tickets


def simulate_payment(buyer_token, ticket_id, amount, quantity, listing_group_id):
    url = f"{API_BASE_URL}/payments/simulate/"
    headers = {'Authorization': f'Bearer {buyer_token}'}
    data = {
        'ticket_id': ticket_id,
        'amount': amount,
        'quantity': quantity,
        'timestamp': 1234567890000,
        'listing_group_id': listing_group_id
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        return response.json()
    print(f"  ✗ Payment failed: {response.status_code} - {response.text[:200]}")
    return None


def create_order(buyer_token, ticket_id, total_amount, quantity, event_name, listing_group_id):
    url = f"{API_BASE_URL}/orders/"
    headers = {'Authorization': f'Bearer {buyer_token}'}
    data = {
        'ticket': ticket_id,
        'total_amount': total_amount,
        'quantity': quantity,
        'event_name': event_name,
        'listing_group_id': listing_group_id
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 201:
        return response.json()
    print(f"  ✗ Order failed: {response.status_code} - {response.text[:200]}")
    return None


def main():
    print("=" * 70)
    print("E2E QA: Multi-Ticket Download - 4 tickets, 4 distinct PDFs")
    print("=" * 70)

    # 1. Create users
    print("\n1. Creating test users...")
    seller, buyer = create_test_users()
    seller_token = get_auth_token('test_seller_multi', 'testpass123')
    buyer_token = get_auth_token('test_buyer_multi', 'testpass123')
    if not seller_token or not buyer_token:
        print("✗ Failed to get auth tokens (ensure server is running)")
        sys.exit(1)
    print(f"  ✓ Seller: {seller.username}, Buyer: {buyer.username}")

    # 2. Upload 4 tickets
    print("\n2. Uploading 4 tickets with PDFs...")
    try:
        event = Event.objects.get(id=EVENT_ID)
    except Event.DoesNotExist:
        print(f"  ✗ Event ID {EVENT_ID} not found. Create an event first.")
        sys.exit(1)

    tickets = upload_tickets(seller_token, EVENT_ID, quantity=4)
    if not tickets or len(tickets) < 4:
        print("✗ Failed to upload 4 tickets")
        sys.exit(1)

    first_ticket = tickets[0]
    listing_group_id = first_ticket.get('listing_group_id')
    if not listing_group_id:
        print("  ✗ No listing_group_id - tickets may not be grouped")
        sys.exit(1)
    print(f"  ✓ Listing Group ID: {listing_group_id}")

    # 3. Simulate payment
    unit_price = 110  # 100 + 10% fee
    total_amount = unit_price * 4
    print(f"\n3. Simulating payment: {total_amount} ILS for 4 tickets...")
    payment = simulate_payment(
        buyer_token,
        first_ticket['id'],
        total_amount,
        quantity=4,
        listing_group_id=listing_group_id
    )
    if not payment or not payment.get('success'):
        print("✗ Payment simulation failed")
        sys.exit(1)
    print("  ✓ Payment simulated")

    # 4. Create order
    print("\n4. Creating order (quantity=4)...")
    order = create_order(
        buyer_token,
        first_ticket['id'],
        total_amount,
        quantity=4,
        event_name=event.name,
        listing_group_id=listing_group_id
    )
    if not order:
        print("✗ Order creation failed")
        sys.exit(1)
    print(f"  ✓ Order created: ID {order['id']}")

    # 5. Assert tickets array
    print("\n5. Asserting order payload contains 4 distinct tickets with 4 distinct PDF URLs...")
    order_tickets = order.get('tickets') or []
    ticket_ids = [t['id'] for t in order_tickets]
    pdf_urls = [t.get('pdf_file_url') for t in order_tickets if t.get('pdf_file_url')]

    print(f"  - tickets array length: {len(order_tickets)}")
    print(f"  - ticket IDs: {ticket_ids}")
    print(f"  - PDF URLs count: {len(pdf_urls)}")

    assert len(order_tickets) == 4, f"Expected 4 tickets, got {len(order_tickets)}"
    assert len(set(ticket_ids)) == 4, f"Expected 4 distinct ticket IDs, got {len(set(ticket_ids))}: {ticket_ids}"
    assert len(pdf_urls) == 4, f"Expected 4 PDF URLs, got {len(pdf_urls)}"
    assert len(set(pdf_urls)) == 4, f"Expected 4 distinct PDF URLs, got {len(set(pdf_urls))}"

    print("  ✓ 4 distinct tickets")
    print("  ✓ 4 distinct pdf_file URLs")

    # 6. Verify DB
    print("\n6. Verifying database...")
    db_order = Order.objects.get(id=order['id'])
    db_ticket_ids = getattr(db_order, 'ticket_ids', []) or []
    print(f"  - Order ticket_ids: {db_ticket_ids}")
    assert len(db_ticket_ids) == 4, f"DB order should have 4 ticket_ids, got {len(db_ticket_ids)}"
    print("  ✓ DB order has 4 ticket_ids")

    print("\n" + "=" * 70)
    print("✅ E2E QA PASSED: Buyer can download ALL 4 tickets after purchase")
    print("=" * 70)
    print("\nConsole output summary:")
    print(f"  - Order ID: {order['id']}")
    print(f"  - Tickets in payload: {len(order_tickets)}")
    print(f"  - Distinct ticket IDs: {len(set(ticket_ids))}")
    print(f"  - Distinct PDF URLs: {len(set(pdf_urls))}")


if __name__ == '__main__':
    main()
