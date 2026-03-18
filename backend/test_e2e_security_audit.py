"""
E2E Security Audit - Actively attempts to hack endpoints to verify defenses.

Test 1 (Malicious File): Upload text file renamed to virus.pdf -> expect 400
Test 2 (IDOR): Buyer B tries to download Buyer A's ticket -> expect 403
Test 3 (Rate Limit): Bot sends 15 offers in 5 seconds -> expect 429

Run (server on port 8000):
    python test_e2e_security_audit.py
"""

import os
import sys
import django
import time
from pathlib import Path
from io import BytesIO

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

import requests
from django.contrib.auth import get_user_model
from django.utils import timezone
from users.models import Ticket, Event, Order

User = get_user_model()
API_BASE_URL = 'http://127.0.0.1:8000/api/users'


def create_valid_pdf():
    """Minimal valid PDF for legitimate uploads."""
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


def get_or_create_event():
    event = Event.objects.first()
    if not event:
        from users.models import Artist
        artist = Artist.objects.first() or Artist.objects.create(name='SecAudit Artist')
        event = Event.objects.create(
            name='SecAudit Event',
            date=timezone.now(),
            venue='מנורה מבטחים',
            city='תל אביב',
            artist=artist
        )
    return event


def main():
    print("=" * 70)
    print("E2E SECURITY AUDIT - Attack Simulation")
    print("=" * 70)

    try:
        requests.get('http://127.0.0.1:8000/', timeout=2)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        print("\n[ERROR] Server not running. Start: python manage.py runserver")
        return 1

    # Setup users
    for uname, email, role in [
        ('sec_audit_seller', 'sec_seller@test.com', 'seller'),
        ('sec_audit_buyer_a', 'sec_buyer_a@test.com', 'buyer'),
        ('sec_audit_buyer_b', 'sec_buyer_b@test.com', 'buyer'),
        ('sec_audit_spammer', 'sec_spammer@test.com', 'buyer'),
    ]:
        u, _ = User.objects.get_or_create(username=uname, defaults={'email': email, 'role': role})
        u.set_password('testpass123')
        u.save()

    seller_token = get_token('sec_audit_seller', 'testpass123')
    buyer_a_token = get_token('sec_audit_buyer_a', 'testpass123')
    buyer_b_token = get_token('sec_audit_buyer_b', 'testpass123')
    spammer_token = get_token('sec_audit_spammer', 'testpass123')
    if not all([seller_token, buyer_a_token, buyer_b_token, spammer_token]):
        print("[FAIL] Could not get tokens")
        return 1

    event = get_or_create_event()
    passed = 0
    failed = 0

    # --- Test 1: Malicious File (text renamed to .pdf) ---
    print("\n" + "-" * 70)
    print("TEST 1: Malicious File - Upload text file renamed to virus.pdf")
    print("-" * 70)
    malicious_content = b"#!/bin/bash\necho pwned\nrm -rf /"
    files = [('pdf_file_0', ('virus.pdf', BytesIO(malicious_content), 'text/plain'))]
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
    if r.status_code == 400:
        err = r.json().get('error', r.text[:80]) if r.headers.get('content-type', '').startswith('application/json') else r.text[:80]
        print(f"  [PASS] Malicious file rejected with 400")
        passed += 1
    else:
        print(f"  [FAIL] Expected 400, got {r.status_code}: {r.text[:150]}")
        failed += 1

    # --- Test 2: IDOR - Buyer B tries to steal Buyer A's ticket ---
    print("\n" + "-" * 70)
    print("TEST 2: IDOR - Buyer B attempts to download Buyer A's ticket")
    print("-" * 70)

    # Seller uploads 1 valid ticket
    pdf_content = create_valid_pdf()
    files = [('pdf_file_0', ('legit.pdf', BytesIO(pdf_content), 'application/pdf'))]
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
        print(f"  [SKIP] Could not upload ticket: {r.status_code}")
        failed += 1
    else:
        resp = r.json()
        ticket_id = resp.get('id')
        listing_group_id = resp.get('listing_group_id')
        Ticket.objects.filter(listing_group_id=listing_group_id).update(status='active')

        # Buyer A purchases the ticket (total = ceil(100 * 1.10) * 1 = 111 per backend validation)
        order_data = {
            'ticket': ticket_id,
            'listing_group_id': listing_group_id,
            'total_amount': '111',
            'quantity': 1,
            'event_name': 'SecAudit Event',
        }
        r_order = requests.post(
            f'{API_BASE_URL}/orders/',
            json=order_data,
            headers={'Authorization': f'Bearer {buyer_a_token}'}
        )
        if r_order.status_code != 201:
            print(f"  [SKIP] Buyer A order failed: {r_order.status_code} - {r_order.text[:100]}")
            failed += 1
        else:
            # Buyer B (different user) tries to download Buyer A's ticket
            r_dl = requests.get(
                f'{API_BASE_URL}/tickets/{ticket_id}/download_pdf/',
                headers={'Authorization': f'Bearer {buyer_b_token}'}
            )
            if r_dl.status_code == 403:
                print(f"  [PASS] Buyer B blocked with 403 Forbidden (IDOR prevented)")
                passed += 1
            else:
                print(f"  [FAIL] Expected 403, got {r_dl.status_code} - IDOR vulnerability!")
                failed += 1

    # --- Test 3: Rate Limit - Bot spams 15 offers ---
    print("\n" + "-" * 70)
    print("TEST 3: Rate Limit - Bot sends 15 offers in 5 seconds")
    print("-" * 70)

    # Need a ticket to make offers on
    pdf_content = create_valid_pdf()
    files = [('pdf_file_0', ('rate_test.pdf', BytesIO(pdf_content), 'application/pdf'))]
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
        print(f"  [SKIP] Could not upload ticket for rate test: {r.status_code}")
        failed += 1
    else:
        ticket_id = r.json().get('id')
        Ticket.objects.filter(id=ticket_id).update(status='active')

        # Spammer sends 15 POST requests to create offers
        got_429 = False
        for i in range(15):
            r_offer = requests.post(
                f'{API_BASE_URL}/offers/',
                json={'ticket': ticket_id, 'amount': str(90 + i), 'quantity': 1},
                headers={'Authorization': f'Bearer {spammer_token}'}
            )
            if r_offer.status_code == 429:
                got_429 = True
                print(f"  [PASS] Request {i+1} blocked with 429 Too Many Requests (rate limit enforced)")
                passed += 1
                break
            elif r_offer.status_code != 201:
                print(f"  [INFO] Request {i+1}: {r_offer.status_code}")
            time.sleep(0.1)

        if not got_429:
            print(f"  [FAIL] Sent 15 requests without receiving 429 - rate limit may not be enforced")
            failed += 1

    # --- Summary ---
    print("\n" + "=" * 70)
    print(f"SECURITY AUDIT SUMMARY: {passed} passed, {failed} failed")
    print("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
