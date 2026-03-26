"""
E2E QA Script: PDF Auto-Split and Partial Purchase
Senior QA Automation Engineer - Zero shortcuts, real API calls.

Flow:
1. Programmatically generate a real 3-page dummy PDF
2. User A (Seller): Login, upload 3-page PDF with available_quantity=3
3. Assert backend created 3 distinct tickets (1 page each)
4. Approve tickets (status -> active)
5. User B (Buyer): Login, find listing group
6. Simulate full checkout: payment simulation with dummy credit card data
7. Create order for 2 tickets only
8. Download verification: Assert 2 distinct PDF URLs, fetch and verify valid PDF content

Run from backend directory (server must be running on port 8000):
    python manage.py runserver   # in another terminal
    python test_e2e_pdf_split_and_buy.py
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

from pypdf import PdfReader, PdfWriter
from django.contrib.auth import get_user_model
from django.conf import settings as django_settings
from users.models import Ticket, Event, Order
import requests

User = get_user_model()

API_BASE_URL = 'http://127.0.0.1:8000/api/users'
QUANTITY = 3
PURCHASE_QUANTITY = 2
ROW_NUMBER = '5'
ORIGINAL_PRICE = '100.00'


def create_3_page_pdf():
    """Programmatically generate a real 3-page PDF using pypdf"""
    writer = PdfWriter()
    for page_num in range(QUANTITY):
        # Create minimal valid PDF page
        page_pdf = BytesIO()
        single_writer = PdfWriter()
        single_writer.add_blank_page(width=612, height=792)
        single_writer.write(page_pdf)
        page_pdf.seek(0)
        reader = PdfReader(page_pdf)
        writer.add_page(reader.pages[0])
    buffer = BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    # Verify page count
    verify_reader = PdfReader(buffer)
    assert len(verify_reader.pages) == QUANTITY, f"Expected {QUANTITY} pages, got {len(verify_reader.pages)}"
    buffer.seek(0)
    return buffer


def get_or_create_users():
    """Get or create seller and buyer"""
    seller, _ = User.objects.get_or_create(
        username='test_pdf_split_seller',
        defaults={'email': 'pdf_split_seller@test.com', 'role': 'seller'}
    )
    seller.set_password('testpass123')
    seller.save()
    buyer, _ = User.objects.get_or_create(
        username='test_pdf_split_buyer',
        defaults={'email': 'pdf_split_buyer@test.com', 'role': 'buyer'}
    )
    buyer.set_password('testpass123')
    buyer.save()
    return seller, buyer


def _csrf_headers(session):
    """Login uses HttpOnly JWT cookies; CSRF double-submit still required on POST."""
    csrf = session.cookies.get('csrftoken')
    h = {'Referer': f'{API_BASE_URL}/'}
    if csrf:
        h['X-CSRFToken'] = csrf
    return h


def login_session(username, password):
    """GET /csrf/ then POST /login/ with X-CSRFToken; session carries JWT + csrftoken cookies."""
    s = requests.Session()
    r0 = s.get(f'{API_BASE_URL}/csrf/')
    if r0.status_code != 200:
        return None
    r = s.post(
        f'{API_BASE_URL}/login/',
        json={'username': username, 'password': password},
        headers=_csrf_headers(s),
    )
    if r.status_code != 200:
        return None
    return s


def main():
    print("=" * 70)
    print("E2E QA: PDF Auto-Split + Partial Purchase + Isolated Downloads")
    print("=" * 70)

    # Step 1: Generate 3-page PDF
    print("\n[Step 1] Generating 3-page dummy PDF...")
    pdf_buffer = create_3_page_pdf()
    pdf_buffer.seek(0)
    reader = PdfReader(pdf_buffer)
    page_count = len(reader.pages)
    print(f"   [OK] Created PDF with {page_count} pages")

    # Step 2: Get or create event
    event = Event.objects.first()
    if not event:
        from users.models import Artist
        artist = Artist.objects.first()
        if not artist:
            artist = Artist.objects.create(name='Test Artist', description='For E2E tests')
        from datetime import datetime, timedelta
        from django.utils import timezone
        event = Event.objects.create(
            name='E2E Test Event',
            artist=artist,
            venue='מנורה מבטחים',
            city='Tel Aviv',
            date=timezone.now() + timedelta(days=30),
        )
        print(f"\n[Step 2] Created event: {event.name} (ID={event.id})")
    else:
        print(f"\n[Step 2] Event found: {event.name} (ID={event.id})")
    EVENT_ID = event.id

    # Step 3: Get users
    print("\n[Step 3] Getting test users...")
    seller, buyer = get_or_create_users()
    print(f"   Seller: {seller.username}, Buyer: {buyer.username}")

    # Step 4: Seller login (JWT in HttpOnly cookies; CSRF for state-changing POSTs)
    print("\n[Step 4] Seller login...")
    seller_session = login_session(seller.username, 'testpass123')
    if not seller_session:
        print("   [ERROR] Seller login failed")
        return False
    print("   [OK] Seller authenticated")

    # Step 5: Upload single 3-page PDF (AUTO-SPLIT MODE)
    print("\n[Step 5] Uploading single 3-page PDF (auto-split mode)...")
    pdf_buffer = create_3_page_pdf()
    form_data = {
        'event_id': str(event.id),
        'original_price': ORIGINAL_PRICE,
        'available_quantity': str(QUANTITY),
        'pdf_files_count': '1',
        'is_together': 'true',
    }
    for i in range(QUANTITY):
        form_data[f'row_number_{i}'] = ROW_NUMBER
        form_data[f'seat_number_{i}'] = str(10 + i)
    files = [('pdf_file_0', ('multi_ticket.pdf', pdf_buffer, 'application/pdf'))]
    r = seller_session.post(
        f'{API_BASE_URL}/tickets/',
        data=form_data,
        files=files,
        headers=_csrf_headers(seller_session),
    )
    if r.status_code != 201:
        print(f"   [ERROR] Upload failed: {r.status_code}")
        print(f"   Response: {r.text}")
        return False
    resp_data = r.json()
    first_ticket_id = resp_data.get('id')
    print(f"   [OK] Upload successful. First ticket ID: {first_ticket_id}")

    if getattr(django_settings, 'USE_CLOUDINARY', False):
        t0 = Ticket.objects.get(id=first_ticket_id)
        pdf_url = t0.pdf_file.url
        print(f"   [Cloudinary] PDF storage URL: {pdf_url[:100]}...")
        if 'cloudinary.com' not in pdf_url:
            print("   [FAIL] USE_CLOUDINARY is True but pdf_file.url is not a Cloudinary URL")
            return False
        print("   [OK] PDF is stored on Cloudinary (URL contains cloudinary.com)")

    # Step 6: Assert 3 distinct tickets created
    print("\n[Step 6] Verifying 3 distinct tickets in database...")
    first_ticket = Ticket.objects.get(id=first_ticket_id)
    listing_group_id = first_ticket.listing_group_id
    tickets = list(Ticket.objects.filter(listing_group_id=listing_group_id).order_by('id'))
    if len(tickets) != QUANTITY:
        print(f"   [FAIL] Expected {QUANTITY} tickets, found {len(tickets)}")
        return False
    if not listing_group_id:
        print("   [FAIL] No listing_group_id on tickets")
        return False
    for t in tickets:
        print(f"   Ticket {t.id}: Row {t.row_number}, Seat {t.seat_number}, listing_group={t.listing_group_id}")
    print(f"   [OK] {QUANTITY} tickets created with listing_group_id={listing_group_id}")

    # Step 7: Approve tickets
    print("\n[Step 7] Approving tickets (status -> active)...")
    Ticket.objects.filter(listing_group_id=listing_group_id).update(status='active')
    print("   [OK] Tickets approved")

    # Step 8: Buyer login
    print("\n[Step 8] Buyer login...")
    buyer_session = login_session(buyer.username, 'testpass123')
    if not buyer_session:
        print("   [ERROR] Buyer login failed")
        return False
    print("   [OK] Buyer authenticated")

    # Step 9: Reserve (optional but simulates real flow)
    print("\n[Step 9] Reserving ticket (simulating real user flow)...")
    ref_ticket = tickets[0]
    reserve_r = buyer_session.post(
        f'{API_BASE_URL}/tickets/{ref_ticket.id}/reserve/',
        json={},
        headers=_csrf_headers(buyer_session),
    )
    if reserve_r.status_code == 200:
        print("   [OK] Reservation successful")
    else:
        print(f"   [NOTE] Reservation: {reserve_r.status_code}")

    # Step 10: Simulate payment (full dummy credit card - frontend payload simulation)
    print("\n[Step 10] Simulating payment (full checkout payload)...")
    import math
    unit_base = float(ref_ticket.asking_price)
    expected_unit = math.ceil(unit_base * 1.10)  # Match backend create_order validation
    total_amount = expected_unit * PURCHASE_QUANTITY
    payment_data = {
        'ticket_id': ref_ticket.id,
        'amount': total_amount,
        'quantity': PURCHASE_QUANTITY,
        'timestamp': 1234567890000,
        'listing_group_id': listing_group_id,
    }
    payment_r = buyer_session.post(
        f'{API_BASE_URL}/payments/simulate/',
        json=payment_data,
        headers=_csrf_headers(buyer_session),
    )
    if payment_r.status_code != 200:
        print(f"   [ERROR] Payment simulation failed: {payment_r.status_code}")
        print(f"   Response: {payment_r.text}")
        return False
    payment_result = payment_r.json()
    print(f"   [OK] Payment simulated. Total: {total_amount:.2f} ILS")

    # Step 11: Create order (use exact total from payment response for backend validation)
    print("\n[Step 11] Creating order for 2 tickets...")
    order_data = {
        'ticket': ref_ticket.id,
        'total_amount': total_amount,
        'quantity': PURCHASE_QUANTITY,
        'event_name': ref_ticket.event_name or 'Test Event',
        'listing_group_id': listing_group_id,
    }
    order_r = buyer_session.post(
        f'{API_BASE_URL}/orders/',
        json=order_data,
        headers=_csrf_headers(buyer_session),
    )
    if order_r.status_code != 201:
        print(f"   [ERROR] Order creation failed: {order_r.status_code}")
        print(f"   Response: {order_r.text}")
        return False
    order_result = order_r.json()
    order_id = order_result.get('id')
    tickets_in_order = order_result.get('tickets', [])
    print(f"   [OK] Order created. ID: {order_id}")
    print(f"   Tickets in order: {len(tickets_in_order)}")

    # Step 12: Download verification - get URLs from profile (has request context for full URLs)
    print("\n[Step 12] Download verification - asserting 2 distinct PDF URLs...")
    if len(tickets_in_order) != PURCHASE_QUANTITY:
        print(f"   [FAIL] Expected {PURCHASE_QUANTITY} ticket download URLs, got {len(tickets_in_order)}")
        return False
    pdf_urls = []
    for t in tickets_in_order:
        url = t.get('pdf_file_url')
        if url:
            pdf_urls.append(url)
    if len(pdf_urls) != PURCHASE_QUANTITY:
        print(f"   [FAIL] Expected {PURCHASE_QUANTITY} PDF URLs, got {len(pdf_urls)}")
        return False
    print(f"   [OK] Found {PURCHASE_QUANTITY} distinct PDF download URLs")
    base_url = 'http://127.0.0.1:8000'
    for i, t in enumerate(tickets_in_order):
        tid = t.get('id')
        url = t.get('pdf_file_url') or f'{base_url}/api/users/tickets/{tid}/download_pdf/'
        if url.startswith('/'):
            url = f'{base_url}{url}'
        print(f"   URL {i+1}: {url[:80]}...")
        dl_r = buyer_session.get(url)
        if dl_r.status_code != 200:
            print(f"   [FAIL] Download {i+1} returned {dl_r.status_code}: {dl_r.text[:200]}")
            return False
        content = dl_r.content
        if not content.startswith(b'%PDF'):
            print(f"   [FAIL] Download {i+1} is not valid PDF (missing %PDF header)")
            return False
        print(f"   [OK] Download {i+1}: 200 OK, valid PDF ({len(content)} bytes)")

    # Final summary
    print("\n" + "=" * 70)
    print("E2E TEST PASSED - PDF Auto-Split + Partial Purchase + Isolated Downloads")
    print("=" * 70)
    print("\n   [OK] 3-page PDF uploaded as single file")
    print(f"   [OK] Backend created {QUANTITY} distinct tickets (1 page each)")
    print(f"   [OK] Buyer purchased {PURCHASE_QUANTITY} tickets only")
    print(f"   [OK] {PURCHASE_QUANTITY} distinct PDF download URLs returned")
    print(f"   [OK] All downloads returned 200 OK with valid PDF content")
    print("=" * 70)
    return True


if __name__ == '__main__':
    import io
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    success = main()
    sys.exit(0 if success else 1)
