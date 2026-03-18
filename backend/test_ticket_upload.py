"""
QA Test Script: Upload 3 tickets and verify listing_group_id
This script simulates uploading 3 tickets to event ID 2 with:
- Row: 5
- Seats: 1, 2, 3
- 3 dummy PDF files

Run this script from the backend directory:
    python test_ticket_upload.py
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
from users.models import Ticket, Event
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

def get_or_create_test_user():
    """Get or create a test seller user"""
    username = 'test_seller_qa'
    try:
        user = User.objects.get(username=username)
        print(f"✓ Found existing test user: {username}")
    except User.DoesNotExist:
        user = User.objects.create_user(
            username=username,
            email='test_seller_qa@example.com',
            password='testpass123',
            role='seller'
        )
        print(f"✓ Created test user: {username}")
    return user

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
    """Verify that event ID 2 exists"""
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
        pdf_filename = f'test_ticket_{i+1}.pdf'
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
    """Verify that 3 tickets were created with the same listing_group_id"""
    print(f"\n🔍 Verifying tickets in database...")
    
    # Find tickets by event, row, and seat numbers
    tickets = Ticket.objects.filter(
        event_id=event_id,
        row_number=row_number,
        seat_number__in=seat_numbers
    ).order_by('seat_number')
    
    if tickets.count() != QUANTITY:
        print(f"✗ Expected {QUANTITY} tickets, found {tickets.count()}")
        return False
    
    print(f"✓ Found {tickets.count()} tickets:")
    
    # Check listing_group_id
    listing_group_ids = set()
    for ticket in tickets:
        listing_group_id = ticket.listing_group_id
        listing_group_ids.add(listing_group_id)
        print(f"  Ticket ID: {ticket.id}")
        print(f"    Row: {ticket.row_number}, Seat: {ticket.seat_number}")
        print(f"    Listing Group ID: {listing_group_id}")
        print(f"    Status: {ticket.status}")
        print(f"    Price: ₪{ticket.original_price}")
        print()
    
    if len(listing_group_ids) == 1:
        print(f"✅ SUCCESS: All {QUANTITY} tickets share the same listing_group_id: {list(listing_group_ids)[0]}")
        return True
    else:
        print(f"✗ FAILURE: Tickets have different listing_group_ids:")
        for group_id in listing_group_ids:
            count = tickets.filter(listing_group_id=group_id).count()
            print(f"  - {group_id}: {count} ticket(s)")
        return False

def cleanup_test_files():
    """Clean up test PDF files"""
    for i in range(QUANTITY):
        pdf_filename = BASE_DIR / f'test_ticket_{i+1}.pdf'
        if pdf_filename.exists():
            pdf_filename.unlink()
            print(f"✓ Cleaned up {pdf_filename.name}")

def main():
    """Main test function"""
    print("=" * 60)
    print("QA Test: Upload 3 Tickets and Verify listing_group_id")
    print("=" * 60)
    
    # Step 1: Verify event exists
    if not verify_event_exists(EVENT_ID):
        print("\n❌ Test aborted: Event does not exist")
        return False
    
    # Step 2: Get or create test user
    user = get_or_create_test_user()
    
    # Step 3: Login and get token
    print(f"\n🔐 Logging in as {user.username}...")
    token = login_and_get_token(user.username, 'testpass123')
    if not token:
        print("\n❌ Test aborted: Could not get authentication token")
        return False
    print("✓ Authentication successful")
    
    # Step 4: Upload tickets
    result = upload_tickets(token, EVENT_ID)
    if not result:
        print("\n❌ Test aborted: Ticket upload failed")
        cleanup_test_files()
        return False
    
    # Step 5: Verify tickets in database
    success = verify_tickets_in_database(EVENT_ID, ROW_NUMBER, SEAT_NUMBERS)
    
    # Step 6: Cleanup
    cleanup_test_files()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ TEST PASSED: All tickets have the same listing_group_id")
    else:
        print("❌ TEST FAILED: Tickets do not share the same listing_group_id")
    print("=" * 60)
    
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

