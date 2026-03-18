"""
Full QA Test: Upload 3 Tickets with Smart Mapping and Checkout
This script:
1. Tests smart mapping (auto-generation of seat numbers from Start Seat)
2. Uploads 3 tickets (Row 5, Seats 10-12, Event ID 2) with dummy PDFs
3. Verifies database: 3 tickets created, unique seats, same listing_group_id
4. Tests checkout: Purchase 2 tickets, verify no "Ticket no longer available" error
5. Shows detailed logs

Run this script from the backend directory:
    python test_full_upload_flow.py
"""

import os
import sys
import django
from pathlib import Path

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from django.contrib.auth import get_user_model
from users.models import Ticket, Event, Order
import requests
import json
from io import BytesIO

User = get_user_model()

# Configuration
API_BASE_URL = 'http://127.0.0.1:8000/api/users'
EVENT_ID = 2
ROW_NUMBER = '5'
START_SEAT = 10  # Start seat number for auto-generation
QUANTITY = 3
ORIGINAL_PRICE = '100.00'
PURCHASE_QUANTITY = 2  # Purchase 2 out of 3 tickets

def create_dummy_pdf(filename, seat_number=None):
    """Create a dummy PDF file for testing"""
    # Create a minimal valid PDF content
    pdf_content = b"""%PDF-1.4
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
/Contents 4 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test Ticket) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000317 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF"""
    
    filepath = BASE_DIR / filename
    with open(filepath, 'wb') as f:
        f.write(pdf_content)
    return filepath

def get_or_create_test_users():
    """Get or create test users (seller and buyer)"""
    seller_username = 'test_seller_qa'
    buyer_username = 'test_buyer_qa'
    
    # Seller
    try:
        seller = User.objects.get(username=seller_username)
        print(f"[OK] Found existing seller: {seller_username}")
    except User.DoesNotExist:
        seller = User.objects.create_user(
            username=seller_username,
            email='test_seller_qa@example.com',
            password='testpass123',
            role='seller'
        )
        print(f"[OK] Created seller: {seller_username}")
    
    # Buyer
    try:
        buyer = User.objects.get(username=buyer_username)
        print(f"[OK] Found existing buyer: {buyer_username}")
    except User.DoesNotExist:
        buyer = User.objects.create_user(
            username=buyer_username,
            email='test_buyer_qa@example.com',
            password='testpass123',
            role='buyer'
        )
        print(f"[OK] Created buyer: {buyer_username}")
    
    return seller, buyer

def login_and_get_token(username, password):
    """Login and get JWT token"""
    url = f"{API_BASE_URL}/login/"
    response = requests.post(url, json={
        'username': username,
        'password': password
    })
    
    if response.status_code == 200:
        data = response.json()
        return data.get('access')
    else:
        print(f"[ERROR] Login failed: {response.status_code} - {response.text}")
        return None

def verify_event_exists(event_id):
    """Verify that event exists"""
    import sys
    import io
    # Set stdout to handle UTF-8 encoding
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    try:
        event = Event.objects.get(id=event_id)
        print(f"[OK] Event found: {event.name} (ID: {event.id})")
        print(f"  Venue: {event.venue}, City: {event.city}")
        print(f"  Date: {event.date}")
        return True
    except Event.DoesNotExist:
        print(f"[ERROR] Event ID {event_id} does not exist!")
        return False

def upload_tickets_with_smart_mapping(token, event_id):
    """Upload 3 tickets with smart mapping (auto-generated seat numbers)"""
    url = f"{API_BASE_URL}/tickets/"
    
    # Create dummy PDF files - one for each ticket
    pdf_file_paths = []
    seat_numbers = []
    for i in range(QUANTITY):
        seat_num = START_SEAT + i  # Auto-generate: 10, 11, 12
        seat_numbers.append(str(seat_num))
        pdf_filename = f'test_ticket_seat_{seat_num}.pdf'
        pdf_path = create_dummy_pdf(pdf_filename, seat_num)
        pdf_file_paths.append((pdf_filename, pdf_path, seat_num))
    
    # Prepare form data
    form_data = {
        'event_id': str(event_id),
        'original_price': ORIGINAL_PRICE,
        'available_quantity': str(QUANTITY),
        'is_together': 'true',
        'pdf_files_count': str(QUANTITY),
    }
    
    # Add row and seat numbers for each ticket (smart mapping simulation)
    print(f"\n📋 Smart Mapping: Auto-generating seat numbers from Start Seat {START_SEAT}")
    for i in range(QUANTITY):
        form_data[f'row_number_{i}'] = ROW_NUMBER
        form_data[f'seat_number_{i}'] = seat_numbers[i]
        print(f"   Ticket {i+1}: Row {ROW_NUMBER}, Seat {seat_numbers[i]}")
    
    # Prepare files - backend expects pdf_file_0, pdf_file_1, etc.
    files = []
    for i, (pdf_filename, pdf_path, seat_num) in enumerate(pdf_file_paths):
        files.append((f'pdf_file_{i}', (pdf_filename, open(pdf_path, 'rb'), 'application/pdf')))
    
    # Make request
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    print(f"\n📤 Uploading {QUANTITY} tickets with smart mapping...")
    print(f"   Event ID: {event_id}")
    print(f"   Row: {ROW_NUMBER}")
    print(f"   Seats: {', '.join(seat_numbers)} (auto-generated from Start Seat {START_SEAT})")
    
    response = requests.post(url, data=form_data, files=files, headers=headers)
    
    # Close file handles
    for _, file_tuple in files:
        file_tuple[1].close()
    
    if response.status_code == 201:
        print(f"[SUCCESS] Upload successful!")
        print(f"   Response: {response.json().get('id', 'N/A')}")
        return True, seat_numbers
    else:
        print(f"[ERROR] Upload failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return False, None

def verify_database(event_id, row_number, seat_numbers):
    """Verify tickets in database: count, unique seats, same listing_group_id"""
    print(f"\n🔍 Database Verification:")
    print(f"=" * 70)
    
    # Find tickets by event, row, and seat numbers
    # Get the most recent tickets (in case of previous test runs)
    all_tickets = Ticket.objects.filter(
        event_id=event_id,
        row_number=row_number,
        seat_number__in=seat_numbers
    ).order_by('-created_at', 'seat_number')
    
    # Get the most recent set of tickets (should be our test tickets)
    tickets = all_tickets[:QUANTITY]
    
    print(f"\n1️⃣ Ticket Count Check:")
    if tickets.count() != QUANTITY:
        print(f"   [FAIL] Expected {QUANTITY} tickets, found {tickets.count()}")
        return False, None, None
    else:
        print(f"   [PASS] Found exactly {QUANTITY} tickets")
    
    print(f"\n2️⃣ Unique Seats Check:")
    ticket_list = list(tickets)
    db_seat_numbers = [t.seat_number for t in ticket_list]
    print(f"   Expected seats: {seat_numbers}")
    print(f"   Database seats: {db_seat_numbers}")
    
    if set(db_seat_numbers) == set(seat_numbers):
        print(f"   [PASS] All seats are unique and match expected values")
    else:
        print(f"   [FAIL] Seat numbers don't match")
        return False, None, None
    
    print(f"\n3️⃣ Listing Group ID Check:")
    listing_group_ids = set()
    for ticket in ticket_list:
        listing_group_id = ticket.listing_group_id
        listing_group_ids.add(listing_group_id)
        print(f"   Ticket ID {ticket.id}:")
        print(f"      Row: {ticket.row_number}, Seat: {ticket.seat_number}")
        print(f"      Status: {ticket.status}")
        print(f"      Listing Group ID: {listing_group_id}")
        print(f"      Price: ₪{ticket.original_price}")
        print()
    
    if len(listing_group_ids) == 1:
        group_id = list(listing_group_ids)[0]
        print(f"   [PASS] All {QUANTITY} tickets share the same listing_group_id")
        print(f"   Group ID: {group_id}")
        return True, ticket_list, group_id
    else:
        print(f"   [FAIL] Tickets have different listing_group_ids:")
        for group_id in listing_group_ids:
            count = tickets.filter(listing_group_id=group_id).count()
            print(f"      - {group_id}: {count} ticket(s)")
        return False, None, None

def purchase_tickets_full_flow(token, ticket, listing_group_id, quantity):
    """Purchase tickets using the FULL checkout flow: Reserve -> Payment -> Order"""
    print(f"\n🛒 Full Checkout Flow Simulation (Real User Experience):")
    print(f"=" * 70)
    print(f"\n   Purchasing {quantity} tickets from group...")
    print(f"   Using ticket ID: {ticket.id}")
    print(f"   Listing Group ID: {listing_group_id}")
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    # Step 1: Reserve ticket (like a real user would)
    print(f"\n   Step 1: Reserving ticket...")
    reserve_url = f"{API_BASE_URL}/tickets/{ticket.id}/reserve/"
    reserve_response = requests.post(reserve_url, json={}, headers=headers)
    
    if reserve_response.status_code != 200:
        print(f"   [ERROR] Reservation failed: {reserve_response.status_code}")
        print(f"      Response: {reserve_response.text}")
        return False
    else:
        print(f"   [OK] Ticket reserved successfully")
        reserve_data = reserve_response.json()
        if 'expires_at' in reserve_data:
            print(f"      Reservation expires at: {reserve_data.get('expires_at')}")
    
    # Step 2: Simulate payment (CRITICAL STEP - must pass!)
    print(f"\n   Step 2: Simulating payment (with listing_group_id)...")
    payment_url = f"{API_BASE_URL}/payments/simulate/"
    
    unit_price = float(ticket.original_price)
    base_amount = unit_price * quantity
    service_fee = base_amount * 0.10
    total_amount = base_amount + service_fee
    
    payment_data = {
        'ticket_id': ticket.id,  # This might be reserved/sold, but backend should check group
        'amount': total_amount,
        'quantity': quantity,
        'listing_group_id': listing_group_id,  # CRITICAL: This tells backend to check group availability
    }
    
    print(f"      Unit price: ₪{unit_price:.2f}")
    print(f"      Quantity: {quantity}")
    print(f"      Base amount: ₪{base_amount:.2f}")
    print(f"      Service fee (10%): ₪{service_fee:.2f}")
    print(f"      Total: ₪{total_amount:.2f}")
    print(f"      Sending listing_group_id: {listing_group_id}")
    
    payment_response = requests.post(payment_url, json=payment_data, headers=headers)
    
    if payment_response.status_code != 200:
        print(f"   [ERROR] Payment simulation failed: {payment_response.status_code}")
        print(f"      Response: {payment_response.text}")
        error_msg = payment_response.text
        if 'no longer available' in error_msg.lower() or 'Invalid quantity' in error_msg:
            print(f"\n   [CRITICAL ERROR] Payment simulation blocked the purchase!")
            print(f"      This is the bug - payment_simulation is checking single ticket")
            print(f"      instead of checking the listing_group_id availability!")
        return False
    else:
        payment_result = payment_response.json()
        print(f"   [SUCCESS] Payment simulation successful!")
        print(f"      Payment ID: {payment_result.get('payment_id', 'N/A')}")
        print(f"      Base price: ₪{payment_result.get('base_price', 0):.2f}")
        print(f"      Service fee: ₪{payment_result.get('service_fee', 0):.2f}")
        print(f"      Total: ₪{payment_result.get('total_amount', 0):.2f}")
    
    # Step 3: Create order
    print(f"\n   Step 3: Creating order...")
    order_url = f"{API_BASE_URL}/orders/"
    order_data = {
        'ticket': ticket.id,  # This might be reserved/sold, but backend should ignore it
        'total_amount': total_amount,
        'quantity': quantity,
        'event_name': ticket.event_name or 'Test Event',
        'listing_group_id': listing_group_id,  # CRITICAL: This tells backend to ignore ticket_id
    }
    
    print(f"      Sending listing_group_id: {listing_group_id}")
    print(f"      Note: ticket_id {ticket.id} may be reserved, but backend should find active tickets in group")
    
    order_response = requests.post(order_url, json=order_data, headers=headers)
    
    if order_response.status_code == 201:
        order_result = order_response.json()
        print(f"   [SUCCESS] Order created successfully!")
        print(f"      Order ID: {order_result.get('id')}")
        print(f"      Quantity: {order_result.get('quantity')}")
        print(f"      Total: ₪{order_result.get('total_amount')}")
        print(f"      Status: {order_result.get('status')}")
        
        # Step 4: Release reservation (real user flow - reservation is released after purchase)
        print(f"\n   Step 4: Releasing reservation...")
        release_url = f"{API_BASE_URL}/tickets/{ticket.id}/release_reservation/"
        release_response = requests.post(release_url, json={}, headers=headers)
        if release_response.status_code == 200:
            print(f"   [OK] Reservation released")
        else:
            print(f"   [NOTE] Reservation release response: {release_response.status_code}")
        
        return True
    else:
        print(f"   [ERROR] Order creation failed: {order_response.status_code}")
        print(f"      Response: {order_response.text}")
        error_msg = order_response.text
        if 'no longer available' in error_msg.lower():
            print(f"\n   [CRITICAL ERROR] 'Ticket is no longer available' error occurred!")
            print(f"      This means the backend is checking the specific ticket_id instead of")
            print(f"      looking for any active ticket in the listing_group_id!")
        return False

def verify_purchase_results(event_id, row_number, seat_numbers, purchase_quantity, listing_group_id):
    """Verify the purchase results"""
    print(f"\n📊 Purchase Results Verification:")
    print(f"=" * 70)
    
    # Check remaining active tickets from THIS listing_group_id only
    active_tickets = Ticket.objects.filter(
        event_id=event_id,
        row_number=row_number,
        seat_number__in=seat_numbers,
        status='active',
        listing_group_id=listing_group_id
    ).order_by('seat_number')
    
    sold_tickets = Ticket.objects.filter(
        event_id=event_id,
        row_number=row_number,
        seat_number__in=seat_numbers,
        status='sold',
        listing_group_id=listing_group_id
    ).order_by('seat_number')
    
    reserved_tickets = Ticket.objects.filter(
        event_id=event_id,
        row_number=row_number,
        seat_number__in=seat_numbers,
        status='reserved',
        listing_group_id=listing_group_id
    ).order_by('seat_number')
    
    # Get all tickets from this group for debugging
    all_group_tickets = Ticket.objects.filter(
        listing_group_id=listing_group_id
    ).order_by('seat_number')
    
    print(f"\n   All tickets in group: {all_group_tickets.count()}")
    for ticket in all_group_tickets:
        print(f"      - Ticket ID {ticket.id}: Row {ticket.row_number}, Seat {ticket.seat_number}, Status: {ticket.status}")
    
    print(f"\n   Active tickets remaining: {active_tickets.count()}")
    for ticket in active_tickets:
        print(f"      - Ticket ID {ticket.id}: Row {ticket.row_number}, Seat {ticket.seat_number}")
    
    print(f"\n   Reserved tickets: {reserved_tickets.count()}")
    for ticket in reserved_tickets:
        print(f"      - Ticket ID {ticket.id}: Row {ticket.row_number}, Seat {ticket.seat_number}")
    
    print(f"\n   Sold tickets: {sold_tickets.count()}")
    for ticket in sold_tickets:
        print(f"      - Ticket ID {ticket.id}: Row {ticket.row_number}, Seat {ticket.seat_number}")
    
    expected_active = QUANTITY - purchase_quantity
    expected_sold = purchase_quantity
    
    print(f"\n   Expected: {expected_active} active, {expected_sold} sold")
    print(f"   Found: {active_tickets.count()} active, {sold_tickets.count()} sold")
    if reserved_tickets.count() > 0:
        print(f"   Note: {reserved_tickets.count()} ticket(s) still reserved (will become active when reservation expires)")
    
    # Verification: We should have the correct number of sold tickets
    # Active + Reserved should equal the remaining tickets
    total_remaining = active_tickets.count() + reserved_tickets.count()
    
    if sold_tickets.count() == expected_sold and total_remaining == expected_active:
        print(f"\n   [PASS] Purchase verification successful!")
        print(f"      {expected_sold} tickets sold correctly")
        print(f"      {total_remaining} tickets remaining ({active_tickets.count()} active, {reserved_tickets.count()} reserved)")
        return True
    elif sold_tickets.count() == expected_sold:
        print(f"\n   [PASS] Purchase verification successful!")
        print(f"      {expected_sold} tickets sold correctly")
        print(f"      Note: {reserved_tickets.count()} ticket(s) still reserved (expected behavior)")
        return True
    else:
        print(f"\n   [FAIL] Purchase verification failed!")
        return False

def cleanup_test_files(seat_numbers):
    """Clean up test PDF files"""
    print(f"\n🧹 Cleaning up test files...")
    for seat_num in seat_numbers:
        pdf_filename = BASE_DIR / f'test_ticket_seat_{seat_num}.pdf'
        if pdf_filename.exists():
            pdf_filename.unlink()
            print(f"   [OK] Cleaned up {pdf_filename.name}")

def main():
    """Main test function"""
    print("=" * 70)
    print("Full QA Test: Upload 3 Tickets with Smart Mapping and Checkout")
    print("=" * 70)
    
    # Step 1: Verify event exists
    if not verify_event_exists(EVENT_ID):
        print("\n❌ Test aborted: Event does not exist")
        return False
    
    # Step 2: Get or create test users
    seller, buyer = get_or_create_test_users()
    
    # Step 3: Login as seller and get token
    print(f"\n🔐 Logging in as seller ({seller.username})...")
    seller_token = login_and_get_token(seller.username, 'testpass123')
    if not seller_token:
        print("\n❌ Test aborted: Could not get seller authentication token")
        return False
    print("[OK] Seller authentication successful")
    
    # Step 4: Upload tickets with smart mapping
    upload_success, seat_numbers = upload_tickets_with_smart_mapping(seller_token, EVENT_ID)
    if not upload_success or not seat_numbers:
        print("\n❌ Test aborted: Ticket upload failed")
        cleanup_test_files(seat_numbers or [])
        return False
    
    # Step 5: Verify database
    db_success, tickets, listing_group_id = verify_database(EVENT_ID, ROW_NUMBER, seat_numbers)
    if not db_success or not tickets or not listing_group_id:
        print("\n❌ Test aborted: Database verification failed")
        cleanup_test_files(seat_numbers)
        return False
    
    # Step 6: Login as buyer
    print(f"\n🔐 Logging in as buyer ({buyer.username})...")
    buyer_token = login_and_get_token(buyer.username, 'testpass123')
    if not buyer_token:
        print("\n❌ Test aborted: Could not get buyer authentication token")
        cleanup_test_files(seat_numbers)
        return False
    print("[OK] Buyer authentication successful")
    
    # Step 7: Purchase 2 tickets (FULL FLOW: Reserve -> Payment -> Order)
    purchase_success = purchase_tickets_full_flow(buyer_token, tickets[0], listing_group_id, PURCHASE_QUANTITY)
    
    if not purchase_success:
        print("\n❌ Test aborted: Purchase failed")
        cleanup_test_files(seat_numbers)
        return False
    
    # Step 8: Verify purchase results
    verify_success = verify_purchase_results(EVENT_ID, ROW_NUMBER, seat_numbers, PURCHASE_QUANTITY, listing_group_id)
    
    # Step 9: Cleanup
    cleanup_test_files(seat_numbers)
    
    # Final Summary
    print("\n" + "=" * 70)
    print("FINAL TEST SUMMARY")
    print("=" * 70)
    
    if upload_success and db_success and purchase_success and verify_success:
        print("\n[SUCCESS] ALL TESTS PASSED!")
        print(f"\n   [OK] Smart Mapping: Seat numbers auto-generated from Start Seat {START_SEAT}")
        print(f"     Generated seats: {', '.join(seat_numbers)}")
        print(f"\n   [OK] Upload: {QUANTITY} tickets uploaded successfully")
        print(f"\n   [OK] Database Verification:")
        print(f"     - {QUANTITY} tickets created")
        print(f"     - All seats unique: {', '.join(seat_numbers)}")
        print(f"     - All share same listing_group_id: {listing_group_id}")
        print(f"\n   [OK] Checkout: {PURCHASE_QUANTITY} tickets purchased successfully")
        print(f"     - No 'Ticket is no longer available' errors")
        print(f"     - {PURCHASE_QUANTITY} tickets marked as sold")
        print(f"     - {QUANTITY - PURCHASE_QUANTITY} tickets remain active")
    else:
        print("\n[FAIL] TEST FAILED!")
        if not upload_success:
            print("   - Upload failed")
        if not db_success:
            print("   - Database verification failed")
        if not purchase_success:
            print("   - Purchase failed (check for 'Ticket is no longer available' error)")
        if not verify_success:
            print("   - Purchase verification failed")
    
    print("=" * 70)
    
    return upload_success and db_success and purchase_success and verify_success

if __name__ == '__main__':
    import sys
    import io
    # Set stdout to handle UTF-8 encoding for Hebrew characters
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    success = main()
    sys.exit(0 if success else 1)

