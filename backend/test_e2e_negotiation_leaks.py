"""
E2E Negotiation Inventory Leak Prevention Test
Proves that creating a new offer auto-cancels previous pending offers on the same listing,
preventing double-lock / inventory leak.

Flow:
1. Seller lists 3 tickets (one listing group)
2. Buyer A creates offer for 1 ticket -> verify 1 pending offer
3. Buyer A creates NEW offer for 2 tickets on same listing
4. Assert: first offer is rejected, second is pending, total pending offers = 1 (not 2)
5. Assert: reserved tickets for Buyer A = 2 (not 3) if reservation is used

Run (with server on port 8000):
    python test_e2e_negotiation_leaks.py
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

import requests
from django.contrib.auth import get_user_model
from django.utils import timezone
from users.models import Ticket, Event, Offer

User = get_user_model()
API_BASE_URL = 'http://127.0.0.1:8000/api/users'


def create_pdf_with_pages(num_pages):
    """Create minimal valid PDF with num_pages."""
    try:
        from pypdf import PdfWriter
        writer = PdfWriter()
        for _ in range(num_pages):
            writer.add_blank_page(width=612, height=792)
        buf = BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except Exception:
        return b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>startxref 178 %%EOF'


def get_token(username, password):
    r = requests.post(f'{API_BASE_URL}/login/', json={'username': username, 'password': password})
    return r.json().get('access') if r.status_code == 200 else None


def get_or_create_event():
    event = Event.objects.first()
    if not event:
        from users.models import Artist
        artist = Artist.objects.first() or Artist.objects.create(name='Leak Test Artist')
        event = Event.objects.create(
            name='Leak Test Event',
            date=timezone.now(),
            venue='מנורה מבטחים',
            city='תל אביב',
            artist=artist
        )
    return event


def main():
    print("=" * 70)
    print("E2E Negotiation Leak Prevention Test")
    print("=" * 70)

    try:
        requests.get('http://127.0.0.1:8000/', timeout=2)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        print("\n[ERROR] Server not running. Start: python manage.py runserver")
        return 1

    # Setup users
    seller, _ = User.objects.get_or_create(
        username='leak_test_seller',
        defaults={'email': 'leak_seller@test.com', 'role': 'seller'}
    )
    seller.set_password('testpass123')
    seller.save()

    buyer_a, _ = User.objects.get_or_create(
        username='leak_test_buyer_a',
        defaults={'email': 'leak_buyer_a@test.com', 'role': 'buyer'}
    )
    buyer_a.set_password('testpass123')
    buyer_a.save()

    seller_token = get_token('leak_test_seller', 'testpass123')
    buyer_token = get_token('leak_test_buyer_a', 'testpass123')
    if not seller_token or not buyer_token:
        print("[FAIL] Could not get tokens")
        return 1

    event = get_or_create_event()

    # 1. Seller lists 3 tickets (one group)
    print("\n[1] Seller uploading 3 tickets...")
    pdf1 = create_pdf_with_pages(1)
    pdf2 = create_pdf_with_pages(1)
    pdf3 = create_pdf_with_pages(1)

    data = {
        'event_id': str(event.id),
        'original_price': '100',
        'available_quantity': '3',
        'section': 'A',
        'row': '5',
        'row_number_0': '5', 'row_number_1': '5', 'row_number_2': '5',
        'seat_number_0': '1', 'seat_number_1': '2', 'seat_number_2': '3',
        'pdf_files_count': '3',
        'split_type': 'כל כמות',
        'ticket_type': 'כרטיס אלקטרוני / PDF',
    }
    files = [
        ('pdf_file_0', ('t1.pdf', BytesIO(pdf1), 'application/pdf')),
        ('pdf_file_1', ('t2.pdf', BytesIO(pdf2), 'application/pdf')),
        ('pdf_file_2', ('t3.pdf', BytesIO(pdf3), 'application/pdf')),
    ]
    r = requests.post(
        f'{API_BASE_URL}/tickets/',
        data=data,
        files=files,
        headers={'Authorization': f'Bearer {seller_token}'}
    )
    if r.status_code != 201:
        print(f"[FAIL] Upload failed: {r.status_code} - {r.text[:150]}")
        return 1

    resp = r.json()
    ticket_id = resp.get('id')
    listing_group_id = resp.get('listing_group_id')
    Ticket.objects.filter(listing_group_id=listing_group_id).update(status='active')
    print(f"    Tickets created, listing_group_id={listing_group_id}")

    # 2. Buyer A creates offer for 1 ticket
    print("\n[2] Buyer A creates offer for 1 ticket...")
    r1 = requests.post(
        f'{API_BASE_URL}/offers/',
        json={'ticket': ticket_id, 'amount': '90', 'quantity': 1},
        headers={'Authorization': f'Bearer {buyer_token}'}
    )
    if r1.status_code != 201:
        print(f"[FAIL] First offer failed: {r1.status_code} - {r1.text[:150]}")
        return 1
    offer1 = r1.json()
    print(f"    Offer 1 created: id={offer1['id']}, quantity=1, status={offer1.get('status')}")

    pending_count = Offer.objects.filter(buyer=buyer_a, status='pending').count()
    if pending_count != 1:
        print(f"[WARN] Expected 1 pending offer, got {pending_count}")

    # 3. Buyer A creates NEW offer for 2 tickets on same listing
    print("\n[3] Buyer A creates NEW offer for 2 tickets on same listing...")
    r2 = requests.post(
        f'{API_BASE_URL}/offers/',
        json={'ticket': ticket_id, 'amount': '180', 'quantity': 2},
        headers={'Authorization': f'Bearer {buyer_token}'}
    )
    if r2.status_code != 201:
        print(f"[FAIL] Second offer failed: {r2.status_code} - {r2.text[:150]}")
        return 1
    offer2 = r2.json()
    print(f"    Offer 2 created: id={offer2['id']}, quantity=2, status={offer2.get('status')}")

    # 4. Assert: first offer is rejected, second is pending
    offer1_refresh = Offer.objects.get(id=offer1['id'])
    offer2_refresh = Offer.objects.get(id=offer2['id'])

    if offer1_refresh.status != 'rejected':
        print(f"[FAIL] First offer should be rejected, got status={offer1_refresh.status}")
        return 1
    print(f"    [OK] First offer auto-cancelled (status=rejected)")

    if offer2_refresh.status != 'pending':
        print(f"[FAIL] Second offer should be pending, got status={offer2_refresh.status}")
        return 1
    print(f"    [OK] Second offer is pending")

    # 5. Assert: total PENDING offers by Buyer A for this listing = 1 (not 2)
    pending_for_listing = Offer.objects.filter(
        buyer=buyer_a,
        status='pending',
        ticket__listing_group_id=listing_group_id
    ).count()
    if pending_for_listing != 1:
        print(f"[FAIL] Expected 1 pending offer for listing, got {pending_for_listing}")
        return 1
    print(f"    [OK] Exactly 1 pending offer for this listing (no double-lock)")

    # 6. Assert: reserved tickets for Buyer A (if any) = at most 2
    reserved_count = Ticket.objects.filter(
        reserved_by=buyer_a,
        status='reserved'
    ).count()
    print(f"    Reserved tickets for Buyer A: {reserved_count}")
    if reserved_count > 2:
        print(f"[FAIL] Inventory leak: {reserved_count} tickets reserved (expected <=2)")
        return 1

    print("\n" + "=" * 70)
    print("[PASS] Negotiation leak prevention verified. No double-lock.")
    print("=" * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
