"""
E2E Cart Abandonment (Ticket Release) Test

Flow:
1. Seller lists 1 ticket
2. Buyer A reserves the ticket (locks it)
3. Manually set reserved_at to 11 minutes ago in DB
4. Call endpoint that triggers release_abandoned_carts() (e.g. GET events/{id}/tickets/)
5. Assert ticket is active again
6. Buyer B purchases the ticket successfully

Run (server on port 8000):
    python test_e2e_cart_abandonment.py
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
from datetime import timedelta
from users.models import Ticket, Event, Order

User = get_user_model()
API_BASE_URL = 'http://127.0.0.1:8000/api/users'


def create_valid_pdf():
    try:
        from pypdf import PdfWriter
        w = PdfWriter()
        w.add_blank_page(width=612, height=792)
        buf = BytesIO()
        w.write(buf)
        return buf.getvalue()
    except Exception:
        return b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>startxref 178 %%EOF'


def get_token(username, password):
    r = requests.post(f'{API_BASE_URL}/login/', json={'username': username, 'password': password})
    return r.json().get('access') if r.status_code == 200 else None


def main():
    print("=" * 70)
    print("E2E Cart Abandonment Test")
    print("=" * 70)

    try:
        requests.get('http://127.0.0.1:8000/', timeout=2)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        print("\n[ERROR] Server not running. Start: python manage.py runserver")
        return 1

    # Setup users
    for uname, email, role in [
        ('cart_seller', 'cart_seller@test.com', 'seller'),
        ('cart_buyer_a', 'cart_buyer_a@test.com', 'buyer'),
        ('cart_buyer_b', 'cart_buyer_b@test.com', 'buyer'),
    ]:
        u, _ = User.objects.get_or_create(username=uname, defaults={'email': email, 'role': role})
        u.set_password('testpass123')
        u.save()

    seller_token = get_token('cart_seller', 'testpass123')
    buyer_a_token = get_token('cart_buyer_a', 'testpass123')
    buyer_b_token = get_token('cart_buyer_b', 'testpass123')
    if not all([seller_token, buyer_a_token, buyer_b_token]):
        print("[FAIL] Could not get tokens")
        return 1

    event = Event.objects.first()
    if not event:
        from users.models import Artist
        artist = Artist.objects.first() or Artist.objects.create(name='Cart Test Artist')
        event = Event.objects.create(
            name='Cart Abandonment Test Event',
            date=timezone.now(),
            venue='מנורה מבטחים',
            city='תל אביב',
            artist=artist
        )

    # 1. Seller uploads 1 ticket
    print("\n[1] Seller uploading 1 ticket...")
    pdf_content = create_valid_pdf()
    files = [('pdf_file_0', ('cart_test.pdf', BytesIO(pdf_content), 'application/pdf'))]
    data = {
        'event_id': str(event.id),
        'original_price': '100',
        'available_quantity': '1',
        'pdf_files_count': '1',
        'split_type': 'כל כמות',
        'ticket_type': 'כרטיס אלקטרוני / PDF',
    }
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
    print(f"    Ticket created: id={ticket_id}")

    # 2. Buyer A reserves the ticket
    print("\n[2] Buyer A reserving ticket...")
    r_res = requests.post(
        f'{API_BASE_URL}/tickets/{ticket_id}/reserve/',
        json={},
        headers={'Authorization': f'Bearer {buyer_a_token}'}
    )
    if r_res.status_code != 200:
        print(f"[FAIL] Reserve failed: {r_res.status_code} - {r_res.text[:150]}")
        return 1
    ticket = Ticket.objects.get(id=ticket_id)
    assert ticket.status == 'reserved', f"Expected reserved, got {ticket.status}"
    print(f"    Ticket reserved by Buyer A")

    # 3. Manually set reserved_at to 11 minutes ago
    print("\n[3] Simulating 11 minutes passed (set reserved_at in past)...")
    old_reserved_at = timezone.now() - timedelta(minutes=11)
    Ticket.objects.filter(id=ticket_id).update(reserved_at=old_reserved_at)
    ticket.refresh_from_db()
    assert ticket.status == 'reserved'
    print(f"    reserved_at set to {old_reserved_at}")

    # 4. Call endpoint that triggers release_abandoned_carts()
    print("\n[4] Triggering cleanup (GET event tickets)...")
    r_tickets = requests.get(
        f'{API_BASE_URL}/events/{event.id}/tickets/',
        headers={'Authorization': f'Bearer {buyer_b_token}'}
    )
    if r_tickets.status_code != 200:
        print(f"[FAIL] Event tickets failed: {r_tickets.status_code}")
        return 1

    ticket.refresh_from_db()
    if ticket.status != 'active':
        print(f"[FAIL] Ticket should be active after cleanup, got status={ticket.status}")
        return 1
    print(f"    [OK] Ticket released back to active")

    # 5. Buyer B purchases the ticket
    print("\n[5] Buyer B purchasing ticket...")
    order_data = {
        'ticket': ticket_id,
        'listing_group_id': listing_group_id,
        'total_amount': '111',
        'quantity': 1,
        'event_name': event.name,
    }
    r_order = requests.post(
        f'{API_BASE_URL}/orders/',
        json=order_data,
        headers={'Authorization': f'Bearer {buyer_b_token}'}
    )
    if r_order.status_code != 201:
        print(f"[FAIL] Buyer B order failed: {r_order.status_code} - {r_order.text[:150]}")
        return 1
    print(f"    [OK] Buyer B purchased successfully")

    print("\n" + "=" * 70)
    print("[PASS] Cart abandonment flow verified.")
    print("=" * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
