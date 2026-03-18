"""
E2E Test: Full Negotiated Checkout Flow
Proves backend correctly applies negotiated offer price (not ticket price) when creating orders.

Flow:
1. User A (Seller) uploads ticket - Asking price: 1000 ILS
2. User B (Buyer) makes Offer for 810 ILS
3. User A accepts Offer
4. User B calls /api/users/orders/ with total_amount=891 (810*1.10) and offer_id
5. Assert: Order created successfully with HTTP 201
"""

import os
import sys
import django
from pathlib import Path
from datetime import timedelta
from django.utils import timezone

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from django.contrib.auth import get_user_model
from users.models import Ticket, Event, Order, Offer
import requests
import json

User = get_user_model()

# Configuration
API_BASE_URL = 'http://127.0.0.1:8000/api/users'

def get_event_id():
    """Get first available event ID"""
    try:
        ev = Event.objects.first()
        return ev.id if ev else 1
    except Exception:
        return 1
LISTING_PRICE = 1000.00  # Seller lists for 1000 ILS
OFFER_AMOUNT = 810.00    # Buyer offers 810 ILS
EXPECTED_TOTAL = 891.00  # 810 + 10% service fee

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
    """Get authentication token"""
    url = f"{API_BASE_URL}/login/"
    response = requests.post(url, json={'username': username, 'password': password})
    if response.status_code == 200:
        return response.json()['access']
    print(f"Failed to get token for {username}: {response.status_code} - {response.text}")
    return None

def create_test_users():
    """Create or get test users - always ensure password is set for login"""
    seller, _ = User.objects.get_or_create(
        username='test_seller_negotiated',
        defaults={'email': 'seller_neg@test.com', 'role': 'seller'}
    )
    seller.role = 'seller'
    seller.set_password('testpass123')
    seller.save()
    
    buyer, _ = User.objects.get_or_create(
        username='test_buyer_negotiated',
        defaults={'email': 'buyer_neg@test.com', 'role': 'buyer'}
    )
    buyer.set_password('testpass123')
    buyer.save()
    
    return seller, buyer

def upload_ticket(seller_token, event_id, price):
    """Upload a ticket for testing"""
    url = f"{API_BASE_URL}/tickets/"
    headers = {'Authorization': f'Bearer {seller_token}'}
    
    pdf_file = create_dummy_pdf()
    files = {'pdf_file': ('ticket.pdf', pdf_file, 'application/pdf')}
    data = {
        'event_id': event_id,
        'original_price': str(price),
        'section': 'A',
        'row': '10',
        'seat_numbers': '1',
        'available_quantity': 1,
        'delivery_method': 'instant'
    }
    response = requests.post(url, data=data, files=files, headers=headers)
    if response.status_code == 201:
        return response.json()
    print(f"Failed to upload ticket: {response.status_code} - {response.text}")
    return None

def create_offer(buyer_token, ticket_id, amount, quantity=1):
    """Create an offer"""
    url = f"{API_BASE_URL}/offers/"
    headers = {'Authorization': f'Bearer {buyer_token}'}
    data = {
        'ticket': ticket_id,
        'amount': str(amount),
        'quantity': quantity
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 201:
        return response.json()
    print(f"Failed to create offer: {response.status_code} - {response.text}")
    return None

def accept_offer(seller_tok, offer_id):
    """Accept an offer"""
    url = f"{API_BASE_URL}/offers/{offer_id}/accept/"
    headers = {'Authorization': f'Bearer {seller_tok}'}
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    print(f"Failed to accept offer: {response.status_code} - {response.text}")
    return None

def simulate_payment(buyer_token, ticket_id, amount, quantity=1):
    """Simulate payment"""
    url = f"{API_BASE_URL}/payment/simulate/"
    headers = {'Authorization': f'Bearer {buyer_token}'}
    data = {
        'ticket_id': ticket_id,
        'amount': amount,
        'quantity': quantity,
        'timestamp': int(timezone.now().timestamp() * 1000)
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        return response.json()
    print(f"Payment simulation failed: {response.status_code} - {response.text}")
    return None

def create_order_with_offer(buyer_token, ticket_id, total_amount, quantity, event_name, offer_id, listing_group_id=None):
    """Create order with offer_id (negotiated price)"""
    url = f"{API_BASE_URL}/orders/"
    headers = {'Authorization': f'Bearer {buyer_token}'}
    data = {
        'ticket': ticket_id,
        'total_amount': total_amount,
        'quantity': quantity,
        'event_name': event_name,
        'offer_id': offer_id  # CRITICAL: Backend uses offer.amount, not ticket.asking_price
    }
    if listing_group_id:
        data['listing_group_id'] = listing_group_id
    
    print(f"\n=== CREATING ORDER WITH OFFER_ID ===")
    print(f"Ticket ID: {ticket_id}")
    print(f"Total Amount: {total_amount}")
    print(f"Quantity: {quantity}")
    print(f"Offer ID: {offer_id}")
    print(f"Payload: {json.dumps(data, indent=2)}")
    print(f"=====================================\n")
    
    response = requests.post(url, json=data, headers=headers)
    return response.status_code, response.json() if response.status_code < 500 else response.text

def main():
    print("=" * 70)
    print("E2E Test: Full Negotiated Checkout Flow")
    print("=" * 70)
    
    # Step 1: Create test users
    print("\n1. Creating test users...")
    seller, buyer = create_test_users()
    seller_token = get_auth_token('test_seller_negotiated', 'testpass123')
    buyer_token = get_auth_token('test_buyer_negotiated', 'testpass123')
    
    if not seller_token or not buyer_token:
        print("[FAIL] Failed to get auth tokens")
        return False
    
    print(f"[OK] Seller: {seller.username} (ID: {seller.id})")
    print(f"[OK] Buyer: {buyer.username} (ID: {buyer.id})")
    
    # Step 2: User A lists a ticket for 1000 ILS
    print(f"\n2. User A listing ticket for {LISTING_PRICE} ILS...")
    ticket = upload_ticket(seller_token, event_id, LISTING_PRICE)
    if not ticket:
        print("[FAIL] Failed to upload ticket")
        return False
    
    ticket_id = ticket['id']
    print(f"[OK] Ticket uploaded: ID {ticket_id}, Price: {LISTING_PRICE} ILS")
    
    # Approve ticket so it's available for offers (bypass admin in test)
    Ticket.objects.filter(id=ticket_id).update(status='active')
    print("[OK] Ticket approved (status=active)")
    
    # Step 3: User B makes an offer for 810 ILS
    print(f"\n3. User B making offer for {OFFER_AMOUNT} ILS...")
    offer = create_offer(buyer_token, ticket_id, OFFER_AMOUNT, quantity=1)
    if not offer:
        print("[FAIL] Failed to create offer")
        return False
    
    offer_id = offer['id']
    print(f"[OK] Offer created: ID {offer_id}, Amount: {offer['amount']} ILS")
    
    # Step 4: User A accepts the offer
    print("\n4. User A accepting offer...")
    accepted_offer = accept_offer(seller_token, offer_id)
    if not accepted_offer:
        print("✗ Failed to accept offer")
        return False
    
    print(f"✓ Offer accepted! Status: {accepted_offer['status']}")
    
    # Step 5: Calculate expected total (810 + 10% = 891)
    base_amount = float(accepted_offer['amount'])
    service_fee = base_amount * 0.10
    expected_total = base_amount + service_fee
    
    print(f"\n5. Payment calculation:")
    print(f"   Base amount (offer): {base_amount} ILS")
    print(f"   Service fee (10%): {service_fee} ILS")
    print(f"   Expected total: {expected_total} ILS")
    
    # Step 6: Simulate payment (with offer_id for negotiated flow)
    print("\n6. Simulating payment (with offer_id)...")
    pay_data = {
        'ticket_id': ticket_id, 'amount': expected_total, 'quantity': 1,
        'timestamp': int(timezone.now().timestamp() * 1000), 'offer_id': offer_id
    }
    pay_r = requests.post(f"{API_BASE_URL}/payments/simulate/", json=pay_data,
                          headers={'Authorization': f'Bearer {buyer_token}'})
    if pay_r.status_code != 200 or not (pay_r.json() or {}).get('success'):
        print(f"Payment simulation failed: {pay_r.status_code} - {pay_r.text[:200]}")
        return False
    print("[OK] Payment simulation successful")

    # Step 7: Create order with offer_id (CRITICAL TEST - must use negotiated price, not ticket price)
    print("\n7. Creating order with offer_id (negotiated price)...")
    event = Event.objects.get(id=event_id)
    listing_group_id = ticket.get('listing_group_id')
    status_code, response_data = create_order_with_offer(
        buyer_token,
        ticket_id,
        expected_total,
        quantity=1,
        event_name=event.name,
        offer_id=offer_id,
        listing_group_id=listing_group_id
    )
    
    print(f"\nResponse Status Code: {status_code}")
    print(f"Response Data: {json.dumps(response_data, indent=2) if isinstance(response_data, dict) else response_data}")
    
    # Step 8: Assertions
    print("\n8. Running assertions...")
    
    if status_code == 201:
        print("[PASS] SUCCESS: Order created with 201 Created status!")
        order_id = response_data.get('id')
        order_total = float(response_data.get('total_amount', 0))
        
        print(f"   Order ID: {order_id}")
        print(f"   Order Total: {order_total} ILS")
        
        # Verify in database
        try:
            db_order = Order.objects.get(id=order_id)
            print(f"   [OK] Order found in database")
            print(f"   [OK] Database total_amount: {float(db_order.total_amount)} ILS")
            
            # Verify ticket status
            db_ticket = Ticket.objects.get(id=ticket_id)
            print(f"   [OK] Ticket status: {db_ticket.status}")
            
            assert abs(order_total - expected_total) < 0.01, f"Total mismatch! Expected {expected_total}, got {order_total}"
            print(f"   [OK] Total amount matches expected value (negotiated price applied)")
            
            return True
        except Exception as e:
            print(f"   [FAIL] Database verification failed: {str(e)}")
            return False
    elif status_code == 400:
        print("[FAIL] Order creation returned 400 Bad Request")
        if isinstance(response_data, dict):
            error_msg = response_data.get('error') or response_data.get('total_amount') or str(response_data)
        else:
            error_msg = str(response_data)
        print(f"   Error: {error_msg}")
        print("\n   This indicates the backend is still validating against ticket.asking_price")
        print("   and rejecting the negotiated price. The backend fix failed!")
        return False
    else:
        print(f"✗ FAILED: Unexpected status code {status_code}")
        print(f"   Response: {response_data}")
        return False

if __name__ == '__main__':
    success = main()
    print("\n" + "=" * 70)
    if success:
        print("[PASS] ALL TESTS PASSED!")
    else:
        print("[FAIL] TESTS FAILED!")
    print("=" * 70)
    sys.exit(0 if success else 1)
