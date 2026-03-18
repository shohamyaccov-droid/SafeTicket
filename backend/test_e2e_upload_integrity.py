"""
E2E Upload Integrity QA Suite - Critical failure points for upload flows.
Tests: single_file mismatch, separate_files flow, concurrency on last ticket.

Run (with server on port 8000):
    python test_e2e_upload_integrity.py
"""

import os
import sys
import django
from pathlib import Path
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

import math
import requests
from django.contrib.auth import get_user_model
from django.utils import timezone
from users.models import Ticket, Event, Order

User = get_user_model()
API_BASE_URL = 'http://127.0.0.1:8000/api/users'


def create_pdf_with_pages(num_pages):
    """Create a minimal valid PDF with exactly num_pages pages."""
    if num_pages < 1:
        num_pages = 1
    try:
        from pypdf import PdfWriter
        writer = PdfWriter()
        for _ in range(num_pages):
            writer.add_blank_page(width=612, height=792)
        buf = BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except Exception as e:
        print(f"[WARN] pypdf create failed: {e}, using fallback")
        if num_pages == 2:
            return b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R 4 0 R]/Count 2>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
4 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000128 00000 n
0000000198 00000 n
trailer<</Size 5/Root 1 0 R>>startxref 268 %%EOF"""
        return create_pdf_with_pages(1)


def get_token(username, password):
    r = requests.post(f'{API_BASE_URL}/login/', json={'username': username, 'password': password})
    return r.json().get('access') if r.status_code == 200 else None


def get_or_create_event():
    event = Event.objects.first()
    if not event:
        from users.models import Artist
        artist = Artist.objects.first() or Artist.objects.create(name='Upload Integrity Artist')
        event = Event.objects.create(
            name='Upload Integrity Event',
            date=timezone.now(),
            venue='מנורה מבטחים',
            city='תל אביב',
            artist=artist
        )
    return event


# ---------------------------------------------------------------------------
# Test A: Mismatch Validation (2-page PDF, quantity=3)
# ---------------------------------------------------------------------------
def test_mismatch_validation():
    """2-page PDF with available_quantity=3 must fail with 400."""
    print("\n" + "=" * 70)
    print("Test A: Mismatch Validation (2-page PDF, quantity=3)")
    print("=" * 70)

    seller, _ = User.objects.get_or_create(
        username='upload_integrity_seller',
        defaults={'email': 'upload_seller@test.com', 'role': 'seller'}
    )
    seller.set_password('testpass123')
    seller.save()

    token = get_token('upload_integrity_seller', 'testpass123')
    if not token:
        print("[FAIL] Could not get token")
        return False

    event = get_or_create_event()
    pdf_2_pages = create_pdf_with_pages(2)

    data = {
        'event_id': str(event.id),
        'original_price': '100',
        'available_quantity': '3',
        'section': 'A',
        'row': '5',
        'row_number_0': '5',
        'row_number_1': '5',
        'row_number_2': '5',
        'seat_number_0': '1',
        'seat_number_1': '2',
        'seat_number_2': '3',
        'pdf_files_count': '1',
        'split_type': 'כל כמות',
        'ticket_type': 'כרטיס אלקטרוני / PDF',
    }
    files = [('pdf_file_0', ('mismatch.pdf', BytesIO(pdf_2_pages), 'application/pdf'))]

    r = requests.post(
        f'{API_BASE_URL}/tickets/',
        data=data,
        files=files,
        headers={'Authorization': f'Bearer {token}'}
    )

    if r.status_code == 400:
        err = r.json().get('error', r.text)
        err_safe = str(err)[:120].encode('ascii', 'replace').decode('ascii')
        if 'עמוד' in str(err) or 'page' in str(err).lower() or 'תואם' in str(err):
            print(f"[PASS] Backend rejected with 400: {err_safe}")
            return True
        print(f"[PASS] Backend rejected with 400: {err_safe}")
        return True
    print(f"[FAIL] Expected 400, got {r.status_code}: {r.text[:200]}")
    return False


# ---------------------------------------------------------------------------
# Test B: Separate Files Flow (2 distinct PDFs, 2 tickets)
# ---------------------------------------------------------------------------
def test_separate_files_flow():
    """2 separate 1-page PDFs, quantity=2 → 2 tickets, one listing_group, no auto-split."""
    print("\n" + "=" * 70)
    print("Test B: Separate Files Flow (2 distinct PDFs)")
    print("=" * 70)

    seller, _ = User.objects.get_or_create(
        username='upload_sep_seller',
        defaults={'email': 'upload_sep@test.com', 'role': 'seller'}
    )
    seller.set_password('testpass123')
    seller.save()

    token = get_token('upload_sep_seller', 'testpass123')
    if not token:
        print("[FAIL] Could not get token")
        return False

    event = get_or_create_event()
    pdf1 = create_pdf_with_pages(1)
    pdf2 = create_pdf_with_pages(1)

    data = {
        'event_id': str(event.id),
        'original_price': '150',
        'available_quantity': '2',
        'section': 'B',
        'row': '10',
        'row_number_0': '10',
        'row_number_1': '10',
        'seat_number_0': '1',
        'seat_number_1': '2',
        'pdf_files_count': '2',
        'split_type': 'כל כמות',
        'ticket_type': 'כרטיס אלקטרוני / PDF',
    }
    files = [
        ('pdf_file_0', ('ticket_a.pdf', BytesIO(pdf1), 'application/pdf')),
        ('pdf_file_1', ('ticket_b.pdf', BytesIO(pdf2), 'application/pdf')),
    ]

    r = requests.post(
        f'{API_BASE_URL}/tickets/',
        data=data,
        files=files,
        headers={'Authorization': f'Bearer {token}'}
    )

    if r.status_code != 201:
        print(f"[FAIL] Expected 201, got {r.status_code}: {r.text[:200]}")
        return False

    resp = r.json()
    ticket_id = resp.get('id')
    listing_group_id = resp.get('listing_group_id')

    tickets = list(Ticket.objects.filter(listing_group_id=listing_group_id).order_by('id'))
    if len(tickets) != 2:
        print(f"[FAIL] Expected 2 tickets in group, got {len(tickets)}")
        return False

    if not listing_group_id:
        print("[FAIL] No listing_group_id - auto-split may have been used incorrectly")
        return False

    # Verify each ticket has its own PDF (different filenames)
    names = [t.pdf_file.name if t.pdf_file else '' for t in tickets]
    if len(set(names)) != 2:
        print(f"[FAIL] Expected 2 distinct PDFs, got: {names}")
        return False

    print(f"[PASS] 2 tickets created, listing_group_id={listing_group_id}, distinct PDFs assigned")
    return True


# ---------------------------------------------------------------------------
# Test C: Concurrency on Last Ticket
# ---------------------------------------------------------------------------
def test_concurrency_last_ticket():
    """2 tickets in group. Buyer A buys 1. Buyer B and C concurrently buy the last 1 → one succeeds, one fails."""
    print("\n" + "=" * 70)
    print("Test C: Concurrency on Last Ticket")
    print("=" * 70)

    seller, _ = User.objects.get_or_create(
        username='upload_conc_seller',
        defaults={'email': 'upload_conc@test.com', 'role': 'seller'}
    )
    seller.set_password('testpass123')
    seller.save()

    for uname in ['upload_conc_buyer_a', 'upload_conc_buyer_b', 'upload_conc_buyer_c']:
        u, _ = User.objects.get_or_create(username=uname, defaults={'email': f'{uname}@test.com', 'role': 'buyer'})
        u.set_password('testpass123')
        u.save()

    event = get_or_create_event()
    pdf1 = create_pdf_with_pages(1)
    pdf2 = create_pdf_with_pages(1)

    token_seller = get_token('upload_conc_seller', 'testpass123')
    if not token_seller:
        print("[FAIL] Could not get seller token")
        return False

    data = {
        'event_id': str(event.id),
        'original_price': '80',
        'available_quantity': '2',
        'section': 'C',
        'row': '3',
        'row_number_0': '3',
        'row_number_1': '3',
        'seat_number_0': '1',
        'seat_number_1': '2',
        'pdf_files_count': '2',
        'split_type': 'כל כמות',
        'ticket_type': 'כרטיס אלקטרוני / PDF',
    }
    files = [
        ('pdf_file_0', ('conc_a.pdf', BytesIO(pdf1), 'application/pdf')),
        ('pdf_file_1', ('conc_b.pdf', BytesIO(pdf2), 'application/pdf')),
    ]

    r = requests.post(
        f'{API_BASE_URL}/tickets/',
        data=data,
        files=files,
        headers={'Authorization': f'Bearer {token_seller}'}
    )
    if r.status_code != 201:
        print(f"[FAIL] Could not create tickets: {r.status_code} - {r.text[:150]}")
        return False

    resp = r.json()
    listing_group_id = resp.get('listing_group_id')
    ticket_id = resp.get('id')

    # Set tickets to active (bypass admin approval for E2E test)
    Ticket.objects.filter(listing_group_id=listing_group_id).update(status='active')

    token_a = get_token('upload_conc_buyer_a', 'testpass123')
    token_b = get_token('upload_conc_buyer_b', 'testpass123')
    token_c = get_token('upload_conc_buyer_c', 'testpass123')
    if not all([token_a, token_b, token_c]):
        print("[FAIL] Could not get buyer tokens")
        return False

    unit = math.ceil(80 * 1.10)

    # Buyer A buys 1 ticket first
    pay_a = requests.post(
        f'{API_BASE_URL}/payments/simulate/',
        json={'ticket_id': ticket_id, 'amount': unit, 'quantity': 1, 'listing_group_id': listing_group_id},
        headers={'Authorization': f'Bearer {token_a}'}
    )
    if pay_a.status_code != 200:
        print(f"[FAIL] Buyer A payment sim failed: {pay_a.status_code}")
        return False

    order_a = requests.post(
        f'{API_BASE_URL}/orders/',
        json={
            'ticket': ticket_id,
            'total_amount': unit,
            'quantity': 1,
            'event_name': event.name,
            'listing_group_id': listing_group_id,
        },
        headers={'Authorization': f'Bearer {token_a}'}
    )
    if order_a.status_code != 201:
        print(f"[FAIL] Buyer A order failed: {order_a.status_code} - {order_a.text[:100]}")
        return False

    print("  Buyer A: purchased 1 ticket successfully")

    # Buyer B and C concurrently try to buy the last ticket
    def do_buy(token, name):
        headers = {'Authorization': f'Bearer {token}'}
        pay_r = requests.post(
            f'{API_BASE_URL}/payments/simulate/',
            json={'ticket_id': ticket_id, 'amount': unit, 'quantity': 1, 'listing_group_id': listing_group_id},
            headers=headers
        )
        if pay_r.status_code != 200:
            return {'name': name, 'status': pay_r.status_code, 'data': pay_r.text[:80]}
        order_r = requests.post(
            f'{API_BASE_URL}/orders/',
            json={
                'ticket': ticket_id,
                'total_amount': unit,
                'quantity': 1,
                'event_name': event.name,
                'listing_group_id': listing_group_id,
            },
            headers=headers
        )
        return {'name': name, 'status': order_r.status_code, 'data': order_r.text[:120] if order_r.status_code != 201 else 'OK'}

    results = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(do_buy, token_b, 'Buyer B')
        f2 = ex.submit(do_buy, token_c, 'Buyer C')
        for f in as_completed([f1, f2]):
            results.append(f.result())

    success_count = sum(1 for r in results if r.get('status') == 201)
    fail_count = sum(1 for r in results if r.get('status') in (400, 500))

    print(f"  Buyer B: status={results[0].get('status')}, data={results[0].get('data', '')[:80]}")
    print(f"  Buyer C: status={results[1].get('status')}, data={results[1].get('data', '')[:80]}")

    if success_count == 1 and fail_count == 1:
        print("[PASS] One succeeded, one failed. Inventory integrity preserved.")
        return True
    print(f"[FAIL] Expected 1 success + 1 failure. Got success={success_count}, fail={fail_count}")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("E2E Upload Integrity QA Suite")
    print("=" * 70)

    try:
        requests.get('http://127.0.0.1:8000/', timeout=2)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        print("\n[ERROR] Server not running. Start: python manage.py runserver")
        return 1

    results = []
    results.append(("A: Mismatch Validation", test_mismatch_validation()))
    results.append(("B: Separate Files Flow", test_separate_files_flow()))
    results.append(("C: Concurrency Last Ticket", test_concurrency_last_ticket()))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, ok in results:
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    all_pass = all(ok for _, ok in results)
    print("=" * 70)
    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())
