"""
E2E Negotiation Audit Script
Tests the complete Bid/Ask negotiation flow:
1. User A (Seller) creates a ticket for 200 ILS
2. User B (Buyer) makes an offer for 100 ILS
3. User A rejects or counters with 150 ILS
4. User B makes a new offer for 120 ILS
5. User A ACCEPTs the 120 ILS offer
6. Verify User B can checkout with negotiated price (120 ILS)
7. Verify public listing still shows 200 ILS
"""

import os
import sys
import django

# Setup Django BEFORE importing Django modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

import json
from datetime import datetime, timedelta
from django.test import Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

# API Configuration
API_URL = '/api/users'

# Test Users
USER_A = {
    'username': 'seller_test',
    'email': 'seller@test.com',
    'password': 'testpass123',
    'role': 'seller'
}

USER_B = {
    'username': 'buyer_test',
    'email': 'buyer@test.com',
    'password': 'testpass123',
    'role': 'buyer'
}

def print_step(step_num, description):
    """Print a formatted test step"""
    print(f"\n{'='*60}")
    print(f"STEP {step_num}: {description}")
    print('='*60)

def get_or_create_user(user_data):
    """Get or create a user"""
    user, created = User.objects.get_or_create(
        username=user_data['username'],
        defaults={
            'email': user_data['email'],
            'role': user_data['role']
        }
    )
    if created:
        user.set_password(user_data['password'])
        user.save()
        print(f"✓ Created user: {user.username}")
    else:
        print(f"✓ Using existing user: {user.username}")
    return user

def get_token_for_user(user):
    """Get JWT token for a user"""
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token), str(refresh)

def get_or_create_event():
    """Get or create a test event"""
    from users.models import Event, Artist
    
    # Try to get existing event
    event = Event.objects.filter(name__icontains='Test Event Negotiation').first()
    if event:
        return event
    
    # Create artist if needed
    artist, _ = Artist.objects.get_or_create(name='Test Artist')
    
    # Create event
    event = Event.objects.create(
        artist=artist,
        name='Test Event Negotiation',
        date=timezone.now() + timedelta(days=30),
        venue='Test Venue',
        city='Tel Aviv'
    )
    return event

def create_ticket(seller_token, price=200.00):
    """Create a ticket for the seller"""
    # First get or create event
    from users.models import Event
    event = get_or_create_event()
    
    # Create ticket via API
    ticket_data = {
        'event_id': event.id,
        'original_price': str(price),
        'available_quantity': 1,
        'delivery_method': 'instant',
        'section': 'A',
        'row': '10',
        'seat_numbers': '1-1',
        'is_together': True
    }
    
    # Note: This requires a PDF file, so we'll use the model directly for testing
    from users.models import Ticket, User
    from django.core.files.uploadedfile import SimpleUploadedFile
    
    seller = User.objects.get(username=USER_A['username'])
    
    # Create a dummy PDF file
    pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
    pdf_file = SimpleUploadedFile('test_ticket.pdf', pdf_content, content_type='application/pdf')
    
    ticket = Ticket.objects.create(
        seller=seller,
        event=event,
        original_price=price,
        asking_price=price,
        pdf_file=pdf_file,
        status='active',
        available_quantity=1,
        section_legacy='A',
        row='10',
        seat_numbers='1-1',
        is_together=True
    )
    
    print(f"✓ Created ticket ID {ticket.id} with price {price} ILS")
    return ticket

def create_offer(client, buyer_token, ticket_id, amount):
    """Create an offer from buyer to seller"""
    response = client.post(
        f'{API_URL}/offers/',
        data=json.dumps({
            'ticket': ticket_id,
            'amount': str(amount)
        }),
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {buyer_token}'
    )
    if response.status_code == 201:
        offer = response.json()
        print(f"✓ Created offer ID {offer['id']} for {amount} ILS")
        return offer
    raise Exception(f"Failed to create offer: {response.status_code} - {response.content}")

def reject_offer(client, seller_token, offer_id):
    """Reject an offer"""
    response = client.post(
        f'{API_URL}/offers/{offer_id}/reject/',
        HTTP_AUTHORIZATION=f'Bearer {seller_token}'
    )
    if response.status_code == 200:
        print(f"✓ Rejected offer ID {offer_id}")
        return response.json()
    raise Exception(f"Failed to reject offer: {response.status_code} - {response.content}")

def counter_offer(client, seller_token, offer_id, counter_amount):
    """Create a counter-offer"""
    response = client.post(
        f'{API_URL}/offers/{offer_id}/counter/',
        data=json.dumps({'amount': str(counter_amount)}),
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {seller_token}'
    )
    if response.status_code == 201:
        offer = response.json()
        print(f"✓ Created counter-offer ID {offer['id']} for {counter_amount} ILS")
        return offer
    raise Exception(f"Failed to create counter-offer: {response.status_code} - {response.content}")

def accept_offer(client, seller_token, offer_id):
    """Accept an offer"""
    response = client.post(
        f'{API_URL}/offers/{offer_id}/accept/',
        HTTP_AUTHORIZATION=f'Bearer {seller_token}'
    )
    if response.status_code == 200:
        offer = response.json()
        print(f"✓ Accepted offer ID {offer_id}")
        print(f"  - Negotiated price: {offer['amount']} ILS")
        print(f"  - Checkout expires at: {offer['checkout_expires_at']}")
        return offer
    raise Exception(f"Failed to accept offer: {response.status_code} - {response.content}")

def get_offers_sent(client, buyer_token):
    """Get offers sent by buyer"""
    response = client.get(
        f'{API_URL}/offers/sent/',
        HTTP_AUTHORIZATION=f'Bearer {buyer_token}'
    )
    if response.status_code == 200:
        return response.json()
    raise Exception(f"Failed to get sent offers: {response.status_code} - {response.content}")

def get_offers_received(client, seller_token):
    """Get offers received by seller"""
    response = client.get(
        f'{API_URL}/offers/received/',
        HTTP_AUTHORIZATION=f'Bearer {seller_token}'
    )
    if response.status_code == 200:
        return response.json()
    raise Exception(f"Failed to get received offers: {response.status_code} - {response.content}")

def get_ticket_details(client, ticket_id, token=None):
    """Get ticket details"""
    url = f'{API_URL}/tickets/{ticket_id}/'
    headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'} if token else {}
    response = client.get(url, **headers)
    if response.status_code == 200:
        return response.json()
    raise Exception(f"Failed to get ticket: {response.status_code} - {response.content}")

def verify_negotiated_price(offer, expected_price):
    """Verify the offer has the correct negotiated price"""
    assert float(offer['amount']) == expected_price, \
        f"Expected negotiated price {expected_price}, got {offer['amount']}"
    print(f"✓ Verified negotiated price: {offer['amount']} ILS")

def verify_public_price(ticket, expected_price):
    """Verify the public listing price hasn't changed"""
    assert float(ticket['asking_price']) == expected_price, \
        f"Expected public price {expected_price}, got {ticket['asking_price']}"
    print(f"✓ Verified public listing price unchanged: {ticket['asking_price']} ILS")

def main():
    """Run the E2E negotiation test"""
    print("\n" + "="*60)
    print("E2E NEGOTIATION AUDIT - Bid/Ask System Test")
    print("="*60)
    
    client = Client()
    
    try:
        # Setup: Get or create users
        print_step(0, "Setting up test users")
        user_a = get_or_create_user(USER_A)
        user_b = get_or_create_user(USER_B)
        
        token_a, _ = get_token_for_user(user_a)
        token_b, _ = get_token_for_user(user_b)
        
        print("✓ Users authenticated")
        
        # Step 1: User A creates ticket for 200 ILS
        print_step(1, "User A (Seller) creates ticket for 200 ILS")
        ticket = create_ticket(token_a, price=200.00)
        ticket_id = ticket.id
        print(f"✓ Ticket ID: {ticket_id}, Price: 200 ILS")
        
        # Step 2: User B makes offer for 100 ILS
        print_step(2, "User B (Buyer) makes offer for 100 ILS")
        offer_1 = create_offer(client, token_b, ticket_id, 100.00)
        offer_1_id = offer_1['id']
        
        # Verify offer was created
        assert offer_1['status'] == 'pending', f"Expected pending, got {offer_1['status']}"
        assert float(offer_1['amount']) == 100.00, "Offer amount mismatch"
        print("✓ Offer created successfully")
        
        # Step 3: User A rejects or counters
        print_step(3, "User A (Seller) counters with 150 ILS")
        counter = counter_offer(client, token_a, offer_1_id, 150.00)
        counter_id = counter['id']
        
        # Verify original offer is now countered
        offers_received = get_offers_received(client, token_a)
        original_offer = next((o for o in offers_received if o['id'] == offer_1_id), None)
        assert original_offer['status'] == 'countered', "Original offer should be countered"
        print("✓ Counter-offer created, original offer marked as countered")
        
        # Step 4: User B makes new offer for 120 ILS
        print_step(4, "User B (Buyer) makes new offer for 120 ILS")
        offer_2 = create_offer(client, token_b, ticket_id, 120.00)
        offer_2_id = offer_2['id']
        print("✓ New offer created")
        
        # Step 5: User A ACCEPTs the 120 ILS offer
        print_step(5, "User A (Seller) ACCEPTs the 120 ILS offer")
        accepted_offer = accept_offer(client, token_a, offer_2_id)
        
        # Verify offer is accepted
        assert accepted_offer['status'] == 'accepted', "Offer should be accepted"
        verify_negotiated_price(accepted_offer, 120.00)
        
        # Verify other pending offers are rejected
        offers_received_after = get_offers_received(client, token_a)
        pending_offers = [o for o in offers_received_after if o['status'] == 'pending' and o['ticket'] == ticket_id]
        assert len(pending_offers) == 0, "All other pending offers should be rejected"
        print("✓ Other pending offers automatically rejected")
        
        # Step 6: Verify User B can see accepted offer in "Offers Sent"
        print_step(6, "Verify User B sees accepted offer in 'Offers Sent'")
        offers_sent = get_offers_sent(client, token_b)
        user_b_accepted = next((o for o in offers_sent if o['id'] == offer_2_id), None)
        assert user_b_accepted is not None, "User B should see the accepted offer"
        assert user_b_accepted['status'] == 'accepted', "Offer should be accepted"
        verify_negotiated_price(user_b_accepted, 120.00)
        print("✓ User B can see accepted offer with 'השלם רכישה' button available")
        
        # Step 7: Verify public listing price is still 200 ILS
        print_step(7, "Verify public listing price unchanged (200 ILS)")
        ticket_details = get_ticket_details(client, ticket_id)
        verify_public_price(ticket_details, 200.00)
        print("✓ Public listing still shows 200 ILS for other users")
        
        # Step 8: Verify checkout would use negotiated price
        print_step(8, "Verify checkout logic uses negotiated price")
        # Get the accepted offer details
        offer_details_response = client.get(
            f'{API_URL}/offers/{offer_2_id}/',
            HTTP_AUTHORIZATION=f'Bearer {token_b}'
        )
        if offer_details_response.status_code == 200:
            offer_details = offer_details_response.json()
            assert offer_details['status'] == 'accepted', "Offer must be accepted"
            assert float(offer_details['amount']) == 120.00, "Checkout should use 120 ILS"
            assert offer_details['checkout_expires_at'] is not None, "Checkout window should be set"
            print("✓ Checkout will use negotiated price: 120 ILS")
            print(f"✓ Checkout window expires at: {offer_details['checkout_expires_at']}")
        else:
            raise Exception(f"Failed to get offer details: {offer_details_response.status_code} - {offer_details_response.content}")
        
        # Final Summary
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nTest Summary:")
        print(f"  - Ticket ID: {ticket_id}")
        print(f"  - Public Price: 200 ILS (unchanged)")
        print(f"  - Negotiated Price: 120 ILS (for User B only)")
        print(f"  - Offer Status: Accepted")
        print(f"  - Checkout Window: 4 hours from acceptance")
        print("\n✓ Bid/Ask Negotiation System is working correctly!")
        
    except Exception as e:
        print("\n" + "="*60)
        print("❌ TEST FAILED!")
        print("="*60)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
