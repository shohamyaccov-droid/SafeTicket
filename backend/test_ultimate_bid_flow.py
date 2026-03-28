"""
Ultimate E2E Bid Flow Test - Simulates exact API calls
Run with: python manage.py test test_ultimate_bid_flow
"""

from django.test import TestCase, Client, override_settings
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import Ticket, Event, Artist, Offer
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
import json

User = get_user_model()

_OFFER_THROTTLE_RF = {
    **settings.REST_FRAMEWORK,
    'DEFAULT_THROTTLE_RATES': {
        **settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}),
        'offers': '1000/min',
    },
}


@override_settings(REST_FRAMEWORK=_OFFER_THROTTLE_RF)
class UltimateBidFlowTest(TestCase):
    """Ultimate E2E test simulating exact API flow"""
    
    def setUp(self):
        """Set up test users"""
        # Create User A (Shoham - Seller)
        self.seller = User.objects.create_user(
            username='shoham_test',
            email='shoham@test.com',
            password='testpass123',
            role='seller'
        )
        
        # Create User B (Ofir - Buyer)
        self.buyer = User.objects.create_user(
            username='ofir_test',
            email='ofir@test.com',
            password='testpass123',
            role='buyer'
        )
        
        # Create event
        artist = Artist.objects.create(name='Ultimate Test Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Ultimate Test Event',
            date=timezone.now() + timedelta(days=30),
            venue='Test Venue',
            city='Tel Aviv'
        )
        
        # Create clients
        self.seller_client = Client()
        self.buyer_client = Client()
        
        seller_token = str(RefreshToken.for_user(self.seller).access_token)
        buyer_token = str(RefreshToken.for_user(self.buyer).access_token)
        
        self.seller_headers = {'HTTP_AUTHORIZATION': f'Bearer {seller_token}'}
        self.buyer_headers = {'HTTP_AUTHORIZATION': f'Bearer {buyer_token}'}
    
    def test_ultimate_bid_flow(self):
        """Test complete bid flow with exact API calls"""
        print("\n" + "="*80)
        print("ULTIMATE E2E BID FLOW TEST")
        print("="*80)
        
        # Step 1: User A (Shoham) creates a ticket with status='active'
        print("\nSTEP 1: User A (Shoham) creates ticket with status='active'")
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
        pdf_file = SimpleUploadedFile('test_ticket.pdf', pdf_content, content_type='application/pdf')
        
        ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=200.00,
            asking_price=200.00,
            pdf_file=pdf_file,
            status='active',  # CRITICAL: Must be active
            available_quantity=1
        )
        print(f"[OK] Ticket created: ID {ticket.id}, Status: {ticket.status}, Seller: {self.seller.username}")
        
        # Step 2: User B (Ofir) calls GET /api/tickets/ to find User A's ticket
        print("\nSTEP 2: User B (Ofir) searches for tickets")
        response = self.buyer_client.get('/api/users/tickets/', **self.buyer_headers)
        self.assertEqual(response.status_code, 200)
        tickets_data = response.json()
        
        # Handle pagination
        tickets_list = tickets_data.get('results', tickets_data) if isinstance(tickets_data, dict) else tickets_data
        if not isinstance(tickets_list, list):
            tickets_list = []
        
        print(f"[OK] Found {len(tickets_list)} tickets")
        
        # Find the ticket we just created
        found_ticket = None
        for t in tickets_list:
            if t.get('id') == ticket.id:
                found_ticket = t
                break
        
        self.assertIsNotNone(found_ticket, f"Ticket {ticket.id} should be visible to buyer")
        print(f"[OK] Ticket {ticket.id} found in ticket list")
        
        # Step 3: User B (Ofir) calls POST /api/users/offers/ on User A's ticket
        print("\nSTEP 3: User B (Ofir) makes offer on User A's ticket")
        offer_amount = 150.00
        response = self.buyer_client.post(
            '/api/users/offers/',
            data=json.dumps({
                'ticket': ticket.id,
                'amount': str(offer_amount)
            }),
            content_type='application/json',
            **self.buyer_headers
        )
        self.assertEqual(response.status_code, 201, 
                        f"Expected 201, got {response.status_code}. Response: {response.content.decode()}")
        offer_data = response.json()
        offer_id = offer_data['id']
        print(f"[OK] Offer created: ID {offer_id}, Amount: {offer_data['amount']} ILS")
        print(f"     Buyer: {offer_data.get('buyer_username', 'N/A')}")
        print(f"     Ticket: {offer_data.get('ticket', 'N/A')}")
        
        # Step 4: User A (Shoham) calls GET /api/users/offers/received/
        print("\nSTEP 4: User A (Shoham) fetches received offers")
        response = self.seller_client.get('/api/users/offers/received/', **self.seller_headers)
        self.assertEqual(response.status_code, 200, 
                        f"Expected 200, got {response.status_code}. Response: {response.content.decode()}")
        
        received_data = response.json()
        
        # Handle pagination
        received_offers = received_data.get('results', received_data) if isinstance(received_data, dict) else received_data
        if not isinstance(received_offers, list):
            received_offers = []
        
        print(f"\n[RAW JSON RESPONSE]:")
        print(json.dumps(received_data, indent=2, default=str))
        
        print(f"\n[PARSED OFFERS COUNT]: {len(received_offers)}")
        
        # CRITICAL ASSERTION: User A must see the offer made by User B
        self.assertGreater(len(received_offers), 0, 
                          f"User A should see at least 1 offer. Got: {len(received_offers)}")
        
        offer_ids = [o.get('id') for o in received_offers]
        self.assertIn(offer_id, offer_ids,
                     f"Offer {offer_id} MUST be in received offers. Found IDs: {offer_ids}")
        
        # Find the specific offer
        found_offer = None
        for o in received_offers:
            if o.get('id') == offer_id:
                found_offer = o
                break
        
        self.assertIsNotNone(found_offer, "Offer should be found in received list")
        print(f"[OK] Offer {offer_id} found in User A's received offers")
        print(f"     Offer details: Buyer={found_offer.get('buyer_username')}, Amount={found_offer.get('amount')}")
        
        # Verify offer details
        self.assertEqual(float(found_offer.get('amount', 0)), offer_amount)
        self.assertEqual(found_offer.get('buyer_username'), self.buyer.username)
        self.assertEqual(found_offer.get('status'), 'pending')
        
        print("\n" + "="*80)
        print("ULTIMATE E2E TEST PASSED - Data Pipeline Working!")
        print("="*80)
        print(f"\nSummary:")
        print(f"  - Ticket created by {self.seller.username}: OK")
        print(f"  - Ticket visible to {self.buyer.username}: OK")
        print(f"  - Offer created by {self.buyer.username}: OK")
        print(f"  - Offer visible to {self.seller.username} in 'Received': OK")
        print(f"  - Data pipeline: WORKING")
