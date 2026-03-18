"""
Comprehensive QA Test: Upload 3 tickets and purchase 2
This script:
1. Uploads 3 tickets (Row 5, Seats 1-3, Event ID 2) with dummy PDFs
2. Verifies they have the same listing_group_id
3. Purchases 2 of them (simulating checkout)
4. Verifies the purchase works without "Ticket is no longer available" errors

Run this script from the backend directory:
    python test_upload_and_purchase.py
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
SEAT_NUMBERS = ['1', '2', '3']
QUANTITY = 3
ORIGINAL_PRICE = '100.00'
PURCHASE_QUANTITY = 2  # Purchase 2 out of 3 tickets

def create_dummy_pdf(filename):
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
        print(f"✓ Found existing seller: {seller_username}")
    except User.DoesNotExist:
        seller = User.objects.create_user(
            username=seller_username,
            email='test_seller_qa@example.com',
            password='testpass123',
            role='seller'
        )
        print(f"✓ Created seller: {seller_username}")
    
    # Buyer
    try:
        buyer = User.objects.get(username=buyer_username)
        print(f"✓ Found existing buyer: {buyer_username}")
    except User.DoesNotExist:
        buyer = User.objects.create_user(
            username=buyer_username,
            email='test_buyer_qa@example.com',
            password='testpass123',
            role='buyer'
        )
        print(f"✓ Created buyer: {buyer_username}")
    
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
        print(f"✗ Login failed: {response.status_code} - {response.text}")
        return None

def verify_event_exists(event_id):
    """Verify that event exists"""
    try:
        event = Event.objects.get(id=event_id)
        print(f"✓ Event found: {event.name} (ID: {event.id})")
        return True
    except Event.DoesNotExist:
        print(f"✗ Event ID {event_id} does not exist!")
        return False

def upload_tickets(token, event_id):
    """Upload 3 tickets with the specified parameters"""
    url = f"{API_BASE_URL}/tickets/"
    
    # Create dummy PDF files
    pdf_file_paths = []
    for i in range(QUANTITY):
        pdf_filename = f'test_ticket_qa_{i+1}.pdf'
        pdf_path = create_dummy_pdf(pdf_filename)
        pdf_file_paths.append((pdf_filename, pdf_path))
    
    # Prepare form data
    form_data = {
        'event_id': str(event_id),
        'original_price': ORIGINAL_PRICE,
        'available_quantity': str(QUANTITY),
        'is_together': 'true',
        'pdf_files_count': str(QUANTITY),
    }
    
    # Add row and seat numbers for each ticket
    for i in range(QUANTITY):
        form_data[f'row_number_{i}'] = ROW_NUMBER
        form_data[f'seat_number_{i}'] = SEAT_NUMBERS[i]
    
    # Prepare files - backend expects pdf_file_0, pdf_file_1, etc.
    files = []
    for i, (pdf_filename, pdf_path) in enumerate(pdf_file_paths):
        files.append((f'pdf_file_{i}', (pdf_filename, open(pdf_path, 'rb'), 'application/pdf')))
    
    # Make request
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    print(f"\n📤 Uploading {QUANTITY} tickets...")
    print(f"   Event ID: {event_id}")
    print(f"   Row: {ROW_NUMBER}")
    print(f"   Seats: {', '.join(SEAT_NUMBERS)}")
    
    response = requests.post(url, data=form_data, files=files, headers=headers)
    
    # Close file handles
    for _, file_tuple in files:
        file_tuple[1].close()
    
    if response.status_code == 201:
        print(f"✓ Upload successful!")
        return response.json()
    else:
        print(f"✗ Upload failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def verify_tickets_in_database(event_id, row_number, seat_numbers):
    """Verify that tickets were created with the same listing_group_id"""
    print(f"\n🔍 Verifying tickets in database...")
    
    # Find tickets by event, row, and seat numbers
    tickets = Ticket.objects.filter(
        event_id=event_id,
        row_number=row_number,
        seat_number__in=seat_numbers
    ).order_by('seat_number')
    
    if tickets.count() != QUANTITY:
        print(f"✗ Expected {QUANTITY} tickets, found {tickets.count()}")
        return None, None
    
    print(f"✓ Found {tickets.count()} tickets:")
    
    # Check listing_group_id
    listing_group_ids = set()
    ticket_list = []
    for ticket in tickets:
        listing_group_id = ticket.listing_group_id
        listing_group_ids.add(listing_group_id)
        ticket_list.append(ticket)
        print(f"  Ticket ID: {ticket.id}")
        print(f"    Row: {ticket.row_number}, Seat: {ticket.seat_number}")
        print(f"    Listing Group ID: {listing_group_id}")
        print(f"    Status: {ticket.status}")
        print(f"    Price: ₪{ticket.original_price}")
        print()
    
    if len(listing_group_ids) == 1:
        group_id = list(listing_group_ids)[0]
        print(f"✅ SUCCESS: All {QUANTITY} tickets share the same listing_group_id: {group_id}")
        return ticket_list, group_id
    else:
        print(f"✗ FAILURE: Tickets have different listing_group_ids:")
        for group_id in listing_group_ids:
            count = tickets.filter(listing_group_id=group_id).count()
            print(f"  - {group_id}: {count} ticket(s)")
        return None, None

def purchase_tickets(token, ticket, listing_group_id, quantity):
    """Purchase tickets using the checkout API"""
    print(f"\n🛒 Purchasing {quantity} tickets...")
    print(f"   Using ticket ID: {ticket.id} (may be sold, but we have listing_group_id)")
    print(f"   Listing Group ID: {listing_group_id}")
    
    # Step 1: Simulate payment
    payment_url = f"{API_BASE_URL}/payments/simulate/"
    unit_price = float(ticket.original_price)
    base_amount = unit_price * quantity
    service_fee = base_amount * 0.10
    total_amount = base_amount + service_fee
    
    payment_data = {
        'ticket_id': ticket.id,  # This might be sold, but backend should ignore it
        'amount': total_amount,
        'quantity': quantity,
    }
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    print(f"   Step 1: Simulating payment (₪{total_amount:.2f})...")
    payment_response = requests.post(payment_url, json=payment_data, headers=headers)
    
    if payment_response.status_code != 200:
        print(f"✗ Payment simulation failed: {payment_response.status_code}")
        print(f"  Response: {payment_response.text}")
        return False
    
    print(f"✓ Payment simulation successful")
    
    # Step 2: Create order
    order_url = f"{API_BASE_URL}/orders/"
    order_data = {
        'ticket': ticket.id,  # This might be sold, but backend should ignore it
        'total_amount': total_amount,
        'quantity': quantity,
        'event_name': ticket.event_name or 'Test Event',
        'listing_group_id': listing_group_id,  # CRITICAL: This tells backend to ignore ticket_id
    }
    
    print(f"   Step 2: Creating order with listing_group_id...")
    print(f"   Note: ticket_id {ticket.id} may be 'sold', but backend should find active tickets in group")
    order_response = requests.post(order_url, json=order_data, headers=headers)
    
    if order_response.status_code == 201:
        order_data = order_response.json()
        print(f"✓ Order created successfully!")
        print(f"   Order ID: {order_data.get('id')}")
        print(f"   Quantity: {order_data.get('quantity')}")
        print(f"   Total: ₪{order_data.get('total_amount')}")
        return True
    else:
        print(f"✗ Order creation failed: {order_response.status_code}")
        print(f"  Response: {order_response.text}")
        error_msg = order_response.text
        if 'no longer available' in error_msg.lower():
            print(f"\n❌ CRITICAL ERROR: 'Ticket is no longer available' error occurred!")
            print(f"   This means the backend is checking the specific ticket_id instead of")
            print(f"   looking for any active ticket in the listing_group_id!")
        return False

def verify_purchase_results(event_id, row_number, seat_numbers, purchase_quantity):
    """Verify the purchase results"""
    print(f"\n🔍 Verifying purchase results...")
    
    # Check remaining active tickets
    active_tickets = Ticket.objects.filter(
        event_id=event_id,
        row_number=row_number,
        seat_number__in=seat_numbers,
        status='active'
    )
    
    sold_tickets = Ticket.objects.filter(
        event_id=event_id,
        row_number=row_number,
        seat_number__in=seat_numbers,
        status='sold'
    )
    
    print(f"   Active tickets remaining: {active_tickets.count()}")
    print(f"   Sold tickets: {sold_tickets.count()}")
    
    expected_active = QUANTITY - purchase_quantity
    expected_sold = purchase_quantity
    
    if active_tickets.count() == expected_active and sold_tickets.count() == expected_sold:
        print(f"✅ SUCCESS: Purchase verification passed!")
        print(f"   Expected {expected_active} active, {expected_sold} sold")
        print(f"   Found {active_tickets.count()} active, {sold_tickets.count()} sold")
        return True
    else:
        print(f"✗ FAILURE: Purchase verification failed!")
        print(f"   Expected {expected_active} active, {expected_sold} sold")
        print(f"   Found {active_tickets.count()} active, {sold_tickets.count()} sold")
        return False

def cleanup_test_files():
    """Clean up test PDF files"""
    for i in range(QUANTITY):
        pdf_filename = BASE_DIR / f'test_ticket_qa_{i+1}.pdf'
        if pdf_filename.exists():
            pdf_filename.unlink()
            print(f"✓ Cleaned up {pdf_filename.name}")

def main():
    """Main test function"""
    print("=" * 70)
    print("Comprehensive QA Test: Upload 3 Tickets and Purchase 2")
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
    print("✓ Seller authentication successful")
    
    # Step 4: Upload tickets
    result = upload_tickets(seller_token, EVENT_ID)
    if not result:
        print("\n❌ Test aborted: Ticket upload failed")
        cleanup_test_files()
        return False
    
    # Step 5: Verify tickets in database
    tickets, listing_group_id = verify_tickets_in_database(EVENT_ID, ROW_NUMBER, SEAT_NUMBERS)
    if not tickets or not listing_group_id:
        print("\n❌ Test aborted: Ticket verification failed")
        cleanup_test_files()
        return False
    
    # Step 6: Login as buyer
    print(f"\n🔐 Logging in as buyer ({buyer.username})...")
    buyer_token = login_and_get_token(buyer.username, 'testpass123')
    if not buyer_token:
        print("\n❌ Test aborted: Could not get buyer authentication token")
        cleanup_test_files()
        return False
    print("✓ Buyer authentication successful")
    
    # Step 7: Purchase 2 tickets
    # Use the first ticket (even if it might be reserved/sold, backend should ignore it)
    purchase_success = purchase_tickets(buyer_token, tickets[0], listing_group_id, PURCHASE_QUANTITY)
    
    if not purchase_success:
        print("\n❌ Test aborted: Purchase failed")
        cleanup_test_files()
        return False
    
    # Step 8: Verify purchase results
    verify_success = verify_purchase_results(EVENT_ID, ROW_NUMBER, SEAT_NUMBERS, PURCHASE_QUANTITY)
    
    # Step 9: Cleanup
    cleanup_test_files()
    
    print("\n" + "=" * 70)
    if purchase_success and verify_success:
        print("✅ ALL TESTS PASSED!")
        print("   - 3 tickets uploaded with same listing_group_id")
        print("   - 2 tickets purchased successfully")
        print("   - No 'Ticket is no longer available' errors")
        print("   - Purchase verification passed")
    else:
        print("❌ TEST FAILED!")
        if not purchase_success:
            print("   - Purchase failed (check for 'Ticket is no longer available' error)")
        if not verify_success:
            print("   - Purchase verification failed")
    print("=" * 70)
    
    return purchase_success and verify_success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)



