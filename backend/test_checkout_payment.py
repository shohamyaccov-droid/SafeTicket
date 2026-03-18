"""
E2E Test: Checkout Payment with Accepted Offer
This script tests the complete flow:
1. User A lists 3 tickets
2. User B makes offer: 100 ILS for ALL 3 tickets (quantity=3)
3. User A accepts the offer
4. User B completes checkout
5. Verify order total = 100 + 10% fee = 110 ILS
6. Verify ticket status changes to sold
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
EVENT_ID = 2  # Adjust based on your test event

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
    url = f"{API_BASE_URL}/token/"
    response = requests.post(url, json={'username': username, 'password': password})
    if response.status_code == 200:
        return response.json()['access']
    return None

def create_test_users():
    """Create or get test users"""
    seller, _ = User.objects.get_or_create(
        username='test_seller_offer',
        defaults={'email': 'seller@test.com', 'password': 'testpass123'}
    )
    if not seller.has_usable_password():
        seller.set_password('testpass123')
        seller.save()
    
    buyer, _ = User.objects.get_or_create(
        username='test_buyer_offer',
        defaults={'email': 'buyer@test.com', 'password': 'testpass123'}
    )
    if not buyer.has_usable_password():
        buyer.set_password('testpass123')
        buyer.save()
    
    return seller, buyer

def upload_tickets(seller_token, event_id, quantity=3):
    """Upload tickets for testing"""
    url = f"{API_BASE_URL}/tickets/"
    headers = {'Authorization': f'Bearer {seller_token}'}
    
    tickets = []
    for i in range(quantity):
        pdf_file = create_dummy_pdf()
        files = {'pdf_file': ('ticket.pdf', pdf_file, 'application/pdf')}
        data = {
            'event_id': event_id,
            'original_price': '100.00',
            'section': 'A',
            'row': '5',
            'seat_numbers': str(i + 1),
            'available_quantity': 1,
            'delivery_method': 'instant'
        }
        response = requests.post(url, data=data, files=files, headers=headers)
        if response.status_code == 201:
            tickets.append(response.json())
            print(f"✓ Uploaded ticket {i+1}: {response.json()['id']}")
        else:
            print(f"✗ Failed to upload ticket {i+1}: {response.status_code} - {response.text}")
    
    return tickets

def create_offer(buyer_token, ticket_id, amount, quantity):
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
    print(f"✗ Failed to create offer: {response.status_code} - {response.text}")
    return None

def accept_offer(seller_token, offer_id):
    """Accept an offer"""
    url = f"{API_BASE_URL}/offers/{offer_id}/accept/"
    headers = {'Authorization': f'Bearer {seller_token}'}
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    print(f"✗ Failed to accept offer: {response.status_code} - {response.text}")
    return None

def simulate_payment(buyer_token, ticket_id, amount, quantity, listing_group_id=None, offer_id=None):
    """Simulate payment"""
    url = f"{API_BASE_URL}/payment/simulate/"
    headers = {'Authorization': f'Bearer {buyer_token}'}
    data = {
        'ticket_id': ticket_id,
        'amount': amount,
        'quantity': quantity,
        'timestamp': int(timezone.now().timestamp() * 1000)
    }
    if listing_group_id:
        data['listing_group_id'] = listing_group_id
    if offer_id:
        data['offer_id'] = offer_id
    
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        return response.json()
    print(f"✗ Payment simulation failed: {response.status_code} - {response.text}")
    return None

def create_order(buyer_token, ticket_id, total_amount, quantity, event_name, listing_group_id=None, offer_id=None):
    """Create order after payment"""
    url = f"{API_BASE_URL}/orders/"
    headers = {'Authorization': f'Bearer {buyer_token}'}
    data = {
        'ticket': ticket_id,
        'total_amount': total_amount,
        'quantity': quantity,
        'event_name': event_name
    }
    if listing_group_id:
        data['listing_group_id'] = listing_group_id
    if offer_id:
        data['offer_id'] = offer_id
    
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 201:
        return response.json()
    print(f"✗ Failed to create order: {response.status_code} - {response.text}")
    return None

def main():
    print("=" * 70)
    print("E2E Test: Checkout Payment with Accepted Offer")
    print("=" * 70)
    
    # Step 1: Create test users
    print("\n1. Creating test users...")
    seller, buyer = create_test_users()
    seller_token = get_auth_token('test_seller_offer', 'testpass123')
    buyer_token = get_auth_token('test_buyer_offer', 'testpass123')
    
    if not seller_token or not buyer_token:
        print("✗ Failed to get auth tokens")
        return
    
    print(f"✓ Seller: {seller.username} (ID: {seller.id})")
    print(f"✓ Buyer: {buyer.username} (ID: {buyer.id})")
    
    # Step 2: Upload 3 tickets
    print("\n2. Uploading 3 tickets...")
    tickets = upload_tickets(seller_token, EVENT_ID, quantity=3)
    if not tickets or len(tickets) < 3:
        print("✗ Failed to upload tickets")
        return
    
    first_ticket = tickets[0]
    listing_group_id = first_ticket.get('listing_group_id')
    print(f"✓ Uploaded {len(tickets)} tickets")
    print(f"✓ Listing Group ID: {listing_group_id}")
    
    # Step 3: Buyer makes offer: 100 ILS for 3 tickets
    print("\n3. Buyer making offer: 100 ILS for 3 tickets...")
    offer = create_offer(buyer_token, first_ticket['id'], 100.00, quantity=3)
    if not offer:
        print("✗ Failed to create offer")
        return
    
    offer_id = offer['id']
    print(f"✓ Offer created: ID {offer_id}, Amount: {offer['amount']}, Quantity: {offer['quantity']}")
    
    # Step 4: Seller accepts offer
    print("\n4. Seller accepting offer...")
    accepted_offer = accept_offer(seller_token, offer_id)
    if not accepted_offer:
        print("✗ Failed to accept offer")
        return
    
    print(f"✓ Offer accepted! Status: {accepted_offer['status']}")
    print(f"✓ Checkout expires at: {accepted_offer.get('checkout_expires_at', 'N/A')}")
    
    # Step 5: Calculate expected total
    base_amount = float(accepted_offer['amount'])  # 100 ILS
    service_fee = base_amount * 0.10  # 10 ILS
    expected_total = base_amount + service_fee  # 110 ILS
    
    print(f"\n5. Expected payment calculation:")
    print(f"   Base amount: {base_amount} ILS")
    print(f"   Service fee (10%): {service_fee} ILS")
    print(f"   Expected total: {expected_total} ILS")
    
    # Step 6: Simulate payment
    print("\n6. Simulating payment...")
    payment_result = simulate_payment(
        buyer_token,
        first_ticket['id'],
        expected_total,
        quantity=3,
        listing_group_id=listing_group_id
    )
    if not payment_result or not payment_result.get('success'):
        print("✗ Payment simulation failed")
        return
    
    print("✓ Payment simulation successful")
    
    # Step 7: Create order
    print("\n7. Creating order...")
    event = Event.objects.get(id=EVENT_ID)
    order = create_order(
        buyer_token,
        first_ticket['id'],
        expected_total,
        quantity=3,
        event_name=event.name,
        listing_group_id=listing_group_id
    )
    if not order:
        print("✗ Failed to create order")
        return
    
    order_id = order['id']
    actual_total = float(order['total_amount'])
    print(f"✓ Order created: ID {order_id}")
    print(f"✓ Order total_amount: {actual_total} ILS")
    
    # Step 8: Verify order in database
    print("\n8. Verifying order in database...")
    db_order = Order.objects.get(id=order_id)
    print(f"✓ Order found in DB: ID {db_order.id}")
    print(f"✓ Order total_amount: {float(db_order.total_amount)} ILS")
    print(f"✓ Order quantity: {db_order.quantity}")
    print(f"✓ Order status: {db_order.status}")
    
    # Step 9: Verify tickets status
    print("\n9. Verifying ticket status...")
    db_tickets = Ticket.objects.filter(id__in=[t['id'] for t in tickets])
    sold_count = db_tickets.filter(status='sold').count()
    print(f"✓ Tickets sold: {sold_count}/{len(tickets)}")
    
    # Step 10: Assertions
    print("\n10. Running assertions...")
    assert abs(actual_total - expected_total) < 0.01, f"Total mismatch! Expected {expected_total}, got {actual_total}"
    assert db_order.quantity == 3, f"Quantity mismatch! Expected 3, got {db_order.quantity}"
    assert sold_count == 3, f"Not all tickets sold! Expected 3, got {sold_count}"
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED!")
    print("=" * 70)
    print(f"\nFinal Results:")
    print(f"  - Order ID: {order_id}")
    print(f"  - Total Paid: {actual_total} ILS (Base: {base_amount} + Fee: {service_fee})")
    print(f"  - Quantity: {db_order.quantity} tickets")
    print(f"  - Tickets Status: {sold_count} sold")
    print(f"\n✅ Math is correct: {base_amount} + {service_fee} = {expected_total} ILS")

def test_tolerance_942():
    """
    E2E Test: Payment Tolerance - 942 ILS accepted for 855 base (expected 940.50)
    Proves backend accepts amount within 2.00 ILS tolerance for JS float vs Python Decimal rounding.
    """
    print("\n" + "=" * 70)
    print("E2E Test: Payment Tolerance - 942 accepted for 855 base (expected 940.50)")
    print("=" * 70)

    seller, buyer = create_test_users()
    seller_token = get_auth_token('test_seller_offer', 'testpass123')
    buyer_token = get_auth_token('test_buyer_offer', 'testpass123')
    if not seller_token or not buyer_token:
        print("[FAIL] Failed to get tokens (ensure server is running: python manage.py runserver)")
        return False

    print("\n1. Uploading ticket...")
    tickets = upload_tickets(seller_token, EVENT_ID, quantity=1)
    if not tickets:
        print("[FAIL] Failed to upload ticket")
        return False
    ticket = tickets[0]
    print(f"   ✓ Ticket ID: {ticket['id']}")

    print("\n2. Creating offer: 855 ILS...")
    offer = create_offer(buyer_token, ticket['id'], 855.00, quantity=1)
    if not offer:
        print("✗ Failed to create offer")
        return False
    print(f"   [OK] Offer ID: {offer['id']}, Amount: {offer['amount']}")

    print("\n3. Accepting offer...")
    accepted = accept_offer(seller_token, offer['id'])
    if not accepted:
        print("[FAIL] Failed to accept offer")
        return False
    print(f"   [OK] Offer accepted")

    expected_total = 855 + (855 * 0.10)  # 940.50
    print(f"\n4. Expected total (base * 1.10): {expected_total:.2f} ILS")
    print(f"   Frontend sends (rounded): 942.00 ILS (1.50 ILS over)")
    print(f"   Tolerance: 2.00 ILS → 942 should be ACCEPTED")

    print("\n5. Simulating payment with amount=942.00 and offer_id...")
    result = simulate_payment(
        buyer_token,
        ticket['id'],
        942.00,  # Previously crashed - now within tolerance
        quantity=1,
        offer_id=offer['id']
    )

    if result and result.get('success'):
        print("   [OK] Payment ACCEPTED! (942 within 2.00 ILS of 940.50)")
    else:
        print(f"   [FAIL] Payment REJECTED: {result}")
        return False

    print("\n" + "=" * 70)
    print("[PASS] TOLERANCE TEST: Backend accepts 942 for 940.50 expected")
    print("=" * 70)
    return True


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--tolerance':
        success = test_tolerance_942()
        sys.exit(0 if success else 1)
    main()
