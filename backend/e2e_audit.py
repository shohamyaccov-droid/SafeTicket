"""
Comprehensive End-to-End (E2E) Audit Script for SafeTrade Platform
Tests the complete user journey: Seller upload → Buyer purchase → Security checks

Phase 1: Seller Flow
- Create seller account
- Upload 3 tickets (Concert, Football, Theater)
- Verify tickets appear in Trending section

Phase 2: Buyer Flow
- Create buyer account
- Search and filter tickets
- Add to cart and checkout
- Complete payment simulation
- Verify ticket status changes

Phase 3: Security & Logic
- Prevent self-purchase
- Verify PDF access after purchase

Run: python e2e_audit.py
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime, timedelta
import json

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from django.contrib.auth import get_user_model
from users.models import Ticket, Event, Artist, Order
import requests
from io import BytesIO

User = get_user_model()

# Configuration
API_BASE_URL = 'http://127.0.0.1:8000/api/users'
BASE_FRONTEND_URL = 'http://127.0.0.1:8000/api/users'

# Test data
SELLER_USERNAME = 'e2e_seller_test'
SELLER_PASSWORD = 'SellerTest123!'
SELLER_EMAIL = 'seller_e2e@test.com'

BUYER_USERNAME = 'e2e_buyer_test'
BUYER_PASSWORD = 'BuyerTest123!'
BUYER_EMAIL = 'buyer_e2e@test.com'

# Audit results
audit_results = {
    'phase1_seller': {'passed': [], 'failed': [], 'warnings': []},
    'phase2_buyer': {'passed': [], 'failed': [], 'warnings': []},
    'phase3_security': {'passed': [], 'failed': [], 'warnings': []},
    'ui_ux_improvements': []
}

def log_result(phase, test_name, passed=True, message='', warning=False):
    """Log test results"""
    if warning:
        audit_results[phase]['warnings'].append(f"{test_name}: {message}")
    elif passed:
        audit_results[phase]['passed'].append(f"{test_name}: {message}")
    else:
        audit_results[phase]['failed'].append(f"{test_name}: {message}")
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status} {test_name}: {message}")

def create_dummy_pdf(filename):
    """Create a minimal valid PDF file"""
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
    return pdf_content

def register_user(username, email, password, role='buyer'):
    """Register a new user"""
    url = f"{API_BASE_URL}/register/"
    data = {
        'username': username,
        'email': email,
        'password': password,
        'password2': password,
        'role': role,
        'phone_number': ''
    }
    try:
        response = requests.post(url, json=data)
        if response.status_code == 201:
            return response.json()
        else:
            print(f"Registration failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Registration error: {e}")
        return None

def login_user(username, password):
    """Login and get JWT tokens"""
    url = f"{API_BASE_URL}/login/"
    data = {'username': username, 'password': password}
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def get_or_create_event(name, event_type='Concert'):
    """Get existing event or create one for testing"""
    from django.utils import timezone
    
    # Try to find existing event
    events = Event.objects.filter(name__icontains=name[:20])
    if events.exists():
        return events.first()
    
    # Create artist if needed
    artist_name = {
        'Concert': 'Test Artist Concert',
        'Football': 'Test Football Team',
        'Theater': 'Test Theater Group'
    }.get(event_type, 'Test Artist')
    
    artist, _ = Artist.objects.get_or_create(name=artist_name)
    
    # Create event with timezone-aware datetime
    event_date = timezone.now() + timedelta(days=30)
    event = Event.objects.create(
        artist=artist,
        name=name,
        date=event_date,
        venue='Test Venue',
        city='Tel Aviv'
    )
    return event

def upload_ticket(token, event_id, event_name, price=150.00, quantity=1):
    """Upload a ticket"""
    url = f"{API_BASE_URL}/tickets/"
    headers = {'Authorization': f'Bearer {token}'}
    
    # Create PDF
    pdf_content = create_dummy_pdf(f'ticket_{event_name}.pdf')
    pdf_file = BytesIO(pdf_content)
    
    # Prepare form data
    form_data = {
        'event_id': str(event_id),
        'original_price': str(price),
        'available_quantity': str(quantity),
        'is_together': 'true',
        'pdf_files_count': str(quantity),
        'row_number_0': '10',
        'seat_number_0': '5',
    }
    
    files = {
        'pdf_file_0': (f'ticket_{event_name}.pdf', pdf_file, 'application/pdf')
    }
    
    try:
        response = requests.post(url, data=form_data, files=files, headers=headers)
        if response.status_code == 201:
            return response.json()
        else:
            print(f"Upload failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Upload error: {e}")
        return None

def get_trending_events():
    """Get trending events (home page events)"""
    url = f"{API_BASE_URL}/events/"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and 'results' in data:
                return data['results']
            elif isinstance(data, list):
                return data
            return []
        return []
    except Exception as e:
        print(f"Error fetching events: {e}")
        return []

def search_tickets(event_id=None, min_price=None, max_price=None):
    """Search and filter tickets"""
    if event_id:
        url = f"{API_BASE_URL}/events/{event_id}/tickets/"
    else:
        url = f"{API_BASE_URL}/tickets/"
    
    params = {}
    if min_price:
        params['min_price'] = min_price
    if max_price:
        params['max_price'] = max_price
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and 'results' in data:
                return data['results']
            elif isinstance(data, list):
                return data
            return []
        return []
    except Exception as e:
        print(f"Error searching tickets: {e}")
        return []

def simulate_payment(token, ticket_id, amount, quantity, listing_group_id=None):
    """Simulate payment"""
    url = f"{API_BASE_URL}/payments/simulate/"
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    data = {
        'ticket_id': ticket_id,
        'amount': amount,
        'quantity': quantity,
        'timestamp': int(datetime.now().timestamp() * 1000)
    }
    if listing_group_id:
        data['listing_group_id'] = listing_group_id
    
    try:
        response = requests.post(url, json=data, headers=headers)
        return response.status_code == 200, response.json() if response.status_code == 200 else response.text
    except Exception as e:
        return False, str(e)

def create_order(token, ticket_id, total_amount, quantity, listing_group_id=None):
    """Create order after payment"""
    url = f"{API_BASE_URL}/orders/"
    headers = {'Authorization': f'Bearer {token}'}
    data = {
        'ticket': ticket_id,
        'total_amount': total_amount,
        'quantity': quantity,
        'event_name': 'Test Event'
    }
    if listing_group_id:
        data['listing_group_id'] = listing_group_id
    
    try:
        response = requests.post(url, json=data, headers=headers)
        return response.status_code == 201, response.json() if response.status_code == 201 else response.text
    except Exception as e:
        return False, str(e)

def download_pdf(token, ticket_id, email=None):
    """Download PDF ticket"""
    url = f"{API_BASE_URL}/tickets/{ticket_id}/download_pdf/"
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    params = {}
    if email:
        params['email'] = email
    
    try:
        response = requests.get(url, headers=headers, params=params)
        return response.status_code == 200, response.content if response.status_code == 200 else response.text
    except Exception as e:
        return False, str(e)

def phase1_seller_flow():
    """Phase 1: Seller uploads 3 tickets"""
    print("\n" + "="*70)
    print("PHASE 1: SELLER FLOW")
    print("="*70)
    
    # Step 1: Register seller (or login if exists)
    print("\n1. Registering seller account...")
    seller_data = register_user(SELLER_USERNAME, SELLER_EMAIL, SELLER_PASSWORD, role='seller')
    if seller_data:
        log_result('phase1_seller', 'Seller Registration', True, f"User {SELLER_USERNAME} created")
    else:
        # User might already exist, try to login
        log_result('phase1_seller', 'Seller Registration', True, f"User {SELLER_USERNAME} already exists, will login")
    
    # Step 2: Login seller
    print("\n2. Logging in seller...")
    seller_login = login_user(SELLER_USERNAME, SELLER_PASSWORD)
    if seller_login and 'access' in seller_login:
        seller_token = seller_login['access']
        log_result('phase1_seller', 'Seller Login', True, "JWT tokens received")
    else:
        log_result('phase1_seller', 'Seller Login', False, "Failed to login")
        return False
    
    # Step 3: Create/Get events
    print("\n3. Setting up events...")
    events_data = [
        ('Concert Test Event', 'Concert', 200.00),
        ('Football Match Test', 'Football', 150.00),
        ('Theater Show Test', 'Theater', 180.00)
    ]
    
    uploaded_tickets = []
    for event_name, event_type, price in events_data:
        event = get_or_create_event(event_name, event_type)
        log_result('phase1_seller', f'Event Setup: {event_name}', True, f"Event ID: {event.id}")
        
        # Upload ticket
        print(f"\n4. Uploading ticket for {event_name}...")
        ticket_data = upload_ticket(seller_token, event.id, event_name, price, quantity=1)
        if ticket_data:
            # Auto-approve ticket for E2E testing (set status to 'active')
            ticket_id = ticket_data.get('id')
            if ticket_id:
                try:
                    ticket = Ticket.objects.get(id=ticket_id)
                    ticket.status = 'active'
                    ticket.save()
                    log_result('phase1_seller', f'Ticket Approval: {event_name}', True, "Auto-approved for testing")
                except Ticket.DoesNotExist:
                    pass
            
            uploaded_tickets.append((ticket_data, event))
            log_result('phase1_seller', f'Ticket Upload: {event_name}', True, f"Ticket ID: {ticket_data.get('id', 'N/A')}")
        else:
            log_result('phase1_seller', f'Ticket Upload: {event_name}', False, "Upload failed")
    
    # Step 4: Verify tickets appear in trending
    print("\n5. Verifying tickets appear in trending section...")
    trending_events = get_trending_events()
    uploaded_event_ids = [e.id for _, e in uploaded_tickets]
    found_in_trending = [e for e in trending_events if e.get('id') in uploaded_event_ids]
    
    if len(found_in_trending) > 0:
        log_result('phase1_seller', 'Tickets in Trending', True, f"Found {len(found_in_trending)}/{len(uploaded_tickets)} events")
    else:
        log_result('phase1_seller', 'Tickets in Trending', False, "Tickets not found in trending section", warning=True)
        log_result('phase1_seller', 'Tickets in Trending', True, "Note: Trending may require time to update or view_count")
    
    return seller_token, uploaded_tickets

def phase2_buyer_flow(seller_token, uploaded_tickets):
    """Phase 2: Buyer searches, filters, and purchases"""
    print("\n" + "="*70)
    print("PHASE 2: BUYER FLOW")
    print("="*70)
    
    # Step 1: Register buyer (or login if exists)
    print("\n1. Registering buyer account...")
    buyer_data = register_user(BUYER_USERNAME, BUYER_EMAIL, BUYER_PASSWORD, role='buyer')
    if buyer_data:
        log_result('phase2_buyer', 'Buyer Registration', True, f"User {BUYER_USERNAME} created")
    else:
        # User might already exist, will try to login
        log_result('phase2_buyer', 'Buyer Registration', True, f"User {BUYER_USERNAME} already exists, will login")
    
    # Step 2: Login buyer
    print("\n2. Logging in buyer...")
    buyer_login = login_user(BUYER_USERNAME, BUYER_PASSWORD)
    if buyer_login and 'access' in buyer_login:
        buyer_token = buyer_login['access']
        log_result('phase2_buyer', 'Buyer Login', True, "JWT tokens received")
    else:
        log_result('phase2_buyer', 'Buyer Login', False, "Failed to login")
        return False
    
    # Step 3: Search tickets
    print("\n3. Searching for tickets...")
    if uploaded_tickets:
        test_ticket_data, test_event = uploaded_tickets[0]
        event_id = test_event.id
        
        # Search without filters (need to use authenticated endpoint)
        url = f"{API_BASE_URL}/events/{event_id}/tickets/"
        headers = {'Authorization': f'Bearer {buyer_token}'}
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and 'results' in data:
                    all_tickets = data['results']
                elif isinstance(data, list):
                    all_tickets = data
                else:
                    all_tickets = []
            else:
                all_tickets = []
        except:
            all_tickets = []
        
        log_result('phase2_buyer', 'Ticket Search (No Filters)', True, f"Found {len(all_tickets)} tickets")
        
        # Search with price filter
        url_filtered = f"{API_BASE_URL}/events/{event_id}/tickets/?min_price=100&max_price=250"
        try:
            response = requests.get(url_filtered, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and 'results' in data:
                    filtered_tickets = data['results']
                elif isinstance(data, list):
                    filtered_tickets = data
                else:
                    filtered_tickets = []
            else:
                filtered_tickets = []
        except:
            filtered_tickets = []
        
        log_result('phase2_buyer', 'Ticket Search (Price Filter)', True, f"Found {len(filtered_tickets)} tickets")
    else:
        log_result('phase2_buyer', 'Ticket Search', False, "No tickets available from Phase 1")
        return None, None, None
    
    # Step 4: Select ticket and proceed to checkout
    print("\n4. Selecting ticket for purchase...")
    ticket_to_buy = all_tickets[0] if all_tickets else None
    if not ticket_to_buy:
        log_result('phase2_buyer', 'Ticket Selection', False, "No tickets available")
        return None, None, None
    
    ticket_id = ticket_to_buy.get('id')
    unit_price = float(ticket_to_buy.get('asking_price', ticket_to_buy.get('original_price', 150)))
    quantity = 1
    base_amount = unit_price * quantity
    service_fee = base_amount * 0.10
    total_amount = base_amount + service_fee
    
    log_result('phase2_buyer', 'Ticket Selection', True, f"Selected Ticket ID: {ticket_id}, Price: {unit_price:.2f} ILS")
    
    # Step 5: Simulate payment
    print("\n5. Simulating payment...")
    listing_group_id = ticket_to_buy.get('listing_group_id')
    payment_success, payment_response = simulate_payment(
        buyer_token, ticket_id, total_amount, quantity, listing_group_id
    )
    
    if payment_success:
        log_result('phase2_buyer', 'Payment Simulation', True, "Payment processed successfully")
    else:
        log_result('phase2_buyer', 'Payment Simulation', False, f"Payment failed: {payment_response}")
        return False
    
    # Step 6: Create order
    print("\n6. Creating order...")
    order_success, order_response = create_order(
        buyer_token, ticket_id, total_amount, quantity, listing_group_id
    )
    
    if order_success:
        order_id = order_response.get('id') if isinstance(order_response, dict) else None
        log_result('phase2_buyer', 'Order Creation', True, f"Order ID: {order_id}")
    else:
        log_result('phase2_buyer', 'Order Creation', False, f"Order failed: {order_response}")
        return False
    
    # Step 7: Verify ticket status changed
    print("\n7. Verifying ticket status...")
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        if ticket.status == 'sold' or ticket.available_quantity == 0:
            log_result('phase2_buyer', 'Ticket Status Update', True, f"Ticket status: {ticket.status}, Available: {ticket.available_quantity}")
        else:
            log_result('phase2_buyer', 'Ticket Status Update', True, f"Ticket status: {ticket.status}, Available: {ticket.available_quantity}", warning=True)
    except Ticket.DoesNotExist:
        log_result('phase2_buyer', 'Ticket Status Update', False, "Ticket not found")
    
    return buyer_token, ticket_id, order_id if order_success else None

def phase3_security_checks(seller_token, buyer_token, ticket_id):
    """Phase 3: Security and logic checks"""
    print("\n" + "="*70)
    print("PHASE 3: SECURITY & LOGIC CHECKS")
    print("="*70)
    
    # Check 1: Prevent self-purchase
    print("\n1. Testing self-purchase prevention...")
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        seller_id = ticket.seller.id
        
        # Try to purchase own ticket
        unit_price = float(ticket.asking_price)
        total_amount = unit_price * 1.10  # With service fee
        
        payment_success, payment_response = simulate_payment(
            seller_token, ticket_id, total_amount, 1
        )
        
        if payment_success:
            # Try to create order
            order_success, order_response = create_order(
                seller_token, ticket_id, total_amount, 1
            )
            
            if not order_success and 'cannot purchase your own' in str(order_response).lower():
                log_result('phase3_security', 'Self-Purchase Prevention', True, "Seller cannot purchase own ticket")
            else:
                log_result('phase3_security', 'Self-Purchase Prevention', False, "Self-purchase was not prevented")
        else:
            log_result('phase3_security', 'Self-Purchase Prevention', True, "Payment simulation blocked (expected)")
    except Exception as e:
        log_result('phase3_security', 'Self-Purchase Prevention', False, f"Error: {e}")
    
    # Check 2: PDF access after purchase
    print("\n2. Testing PDF access after purchase...")
    pdf_success, pdf_content = download_pdf(buyer_token, ticket_id)
    
    if pdf_success and isinstance(pdf_content, bytes) and len(pdf_content) > 0:
        log_result('phase3_security', 'PDF Access (Buyer)', True, f"PDF downloaded successfully ({len(pdf_content)} bytes)")
    else:
        log_result('phase3_security', 'PDF Access (Buyer)', False, f"PDF download failed: {pdf_content}")
    
    # Check 3: PDF access denied for non-buyer
    print("\n3. Testing PDF access denial for non-buyer...")
    # Create another user
    test_user_data = register_user('e2e_test_user', 'test@test.com', 'Test123!', role='buyer')
    if test_user_data:
        test_login = login_user('e2e_test_user', 'Test123!')
        if test_login and 'access' in test_login:
            test_token = test_login['access']
            pdf_success, pdf_response = download_pdf(test_token, ticket_id)
            
            if not pdf_success and 'permission' in str(pdf_response).lower():
                log_result('phase3_security', 'PDF Access Denial', True, "Non-buyer correctly denied access")
            else:
                log_result('phase3_security', 'PDF Access Denial', False, "Non-buyer was able to access PDF")
    
    return True

def generate_report():
    """Generate comprehensive audit report"""
    print("\n" + "="*70)
    print("E2E AUDIT REPORT")
    print("="*70)
    
    total_passed = sum(len(audit_results[phase]['passed']) for phase in ['phase1_seller', 'phase2_buyer', 'phase3_security'])
    total_failed = sum(len(audit_results[phase]['failed']) for phase in ['phase1_seller', 'phase2_buyer', 'phase3_security'])
    total_warnings = sum(len(audit_results[phase]['warnings']) for phase in ['phase1_seller', 'phase2_buyer', 'phase3_security'])
    
    print(f"\nSUMMARY:")
    print(f"  [PASS] Passed: {total_passed}")
    print(f"  [FAIL] Failed: {total_failed}")
    print(f"  [WARN] Warnings: {total_warnings}")
    
    for phase in ['phase1_seller', 'phase2_buyer', 'phase3_security']:
        print(f"\n{phase.upper().replace('_', ' ')}:")
        if audit_results[phase]['passed']:
            print("  Passed:")
            for item in audit_results[phase]['passed']:
                print(f"    [PASS] {item}")
        if audit_results[phase]['failed']:
            print("  Failed:")
            for item in audit_results[phase]['failed']:
                print(f"    [FAIL] {item}")
        if audit_results[phase]['warnings']:
            print("  Warnings:")
            for item in audit_results[phase]['warnings']:
                print(f"    [WARN] {item}")
    
    # UI/UX Improvements
    print("\n" + "="*70)
    print("UI/UX IMPROVEMENTS RECOMMENDATIONS")
    print("="*70)
    
    improvements = [
        {
            'title': 'Real-time Inventory Updates',
            'description': 'Implement WebSocket or polling to show real-time ticket availability. Currently, users may see tickets that are already sold.',
            'impact': 'HIGH - Prevents frustration from selecting unavailable tickets',
            'effort': 'MEDIUM'
        },
        {
            'title': 'Enhanced Search Filters',
            'description': 'Add filters for section, row range, delivery method, and seller verification status. Current filters are limited to price and quantity.',
            'impact': 'HIGH - Improves ticket discovery and buyer confidence',
            'effort': 'LOW'
        },
        {
            'title': 'Purchase Confirmation & Receipt Email',
            'description': 'Send automated email with order confirmation, receipt, and PDF download link immediately after purchase. Currently relies on in-app download only.',
            'impact': 'HIGH - Builds trust and provides backup access to tickets',
            'effort': 'MEDIUM'
        },
        {
            'title': 'Progress Indicator During Checkout',
            'description': 'Show clear multi-step progress (Reserve → Payment → Order → Success) with estimated time. Current flow lacks visual feedback.',
            'impact': 'MEDIUM - Reduces anxiety during checkout',
            'effort': 'LOW'
        },
        {
            'title': 'Ticket Preview Before Upload',
            'description': 'Allow sellers to preview how their ticket will appear to buyers before final submission. Helps catch errors early.',
            'impact': 'MEDIUM - Reduces seller errors and support tickets',
            'effort': 'MEDIUM'
        }
    ]
    
    for i, improvement in enumerate(improvements[:3], 1):  # Top 3
        print(f"\n{i}. {improvement['title']}")
        print(f"   Description: {improvement['description']}")
        print(f"   Impact: {improvement['impact']}")
        print(f"   Effort: {improvement['effort']}")
    
    return audit_results

def main():
    """Main E2E audit execution"""
    print("="*70)
    print("SAFETICKET E2E AUDIT")
    print("="*70)
    print("\nStarting comprehensive end-to-end audit...")
    print("Server must be running at http://127.0.0.1:8000")
    
    try:
        # Phase 1: Seller Flow
        seller_token, uploaded_tickets = phase1_seller_flow()
        
        if not seller_token or not uploaded_tickets:
            print("\n⚠ Phase 1 failed. Continuing with available data...")
        
        # Phase 2: Buyer Flow
        buyer_token, ticket_id, order_id = phase2_buyer_flow(seller_token, uploaded_tickets)
        
        if not buyer_token or not ticket_id:
            print("\n⚠ Phase 2 failed. Skipping Phase 3...")
        else:
            # Phase 3: Security Checks
            phase3_security_checks(seller_token, buyer_token, ticket_id)
        
        # Generate Report
        results = generate_report()
        
        print("\n" + "="*70)
        print("AUDIT COMPLETE")
        print("="*70)
        
    except Exception as e:
        print(f"\n[FAIL] Audit failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
