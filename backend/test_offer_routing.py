"""
E2E Test for Offer Routing Logic (Received vs Sent)
Run with: python manage.py test test_offer_routing
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import Ticket, Event, Artist, Offer
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
import json

User = get_user_model()


class OfferRoutingTest(TestCase):
    """Test that offers appear in correct tabs (Received vs Sent)"""
    
    def setUp(self):
        """Set up test users and ticket"""
        # Create users
        self.seller = User.objects.create_user(
            username='seller_routing_test',
            email='seller@routing.com',
            password='testpass123',
            role='seller'
        )
        
        self.buyer = User.objects.create_user(
            username='buyer_routing_test',
            email='buyer@routing.com',
            password='testpass123',
            role='buyer'
        )
        
        # Create event and ticket
        artist = Artist.objects.create(name='Routing Test Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Routing Test Event',
            date=timezone.now() + timedelta(days=30),
            venue='Test Venue',
            city='Tel Aviv'
        )
        
        # Create ticket owned by seller
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
        pdf_file = SimpleUploadedFile('test_ticket.pdf', pdf_content, content_type='application/pdf')
        
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=200.00,
            asking_price=200.00,
            pdf_file=pdf_file,
            status='active',
            available_quantity=1
        )
        
        # Create clients with authentication
        self.seller_client = Client()
        self.buyer_client = Client()
        
        seller_token = str(RefreshToken.for_user(self.seller).access_token)
        buyer_token = str(RefreshToken.for_user(self.buyer).access_token)
        
        self.seller_headers = {'HTTP_AUTHORIZATION': f'Bearer {seller_token}'}
        self.buyer_headers = {'HTTP_AUTHORIZATION': f'Bearer {buyer_token}'}
    
    def test_offer_routing_logic(self):
        """Test that offers appear in correct tabs"""
        print("\n" + "="*60)
        print("E2E OFFER ROUTING TEST")
        print("="*60)
        
        # Step 1: Buyer creates an offer
        print("\nSTEP 1: Buyer creates offer for 150 ILS")
        response = self.buyer_client.post(
            '/api/users/offers/',
            data=json.dumps({
                'ticket': self.ticket.id,
                'amount': '150.00'
            }),
            content_type='application/json',
            **self.buyer_headers
        )
        self.assertEqual(response.status_code, 201)
        offer = response.json()
        offer_id = offer['id']
        print(f"[OK] Offer created: ID {offer_id}")
        
        # Step 2: Verify Seller sees offer in "Received" (not Sent)
        print("\nSTEP 2: Seller checks 'Received' offers")
        response = self.seller_client.get('/api/users/offers/received/', **self.seller_headers)
        self.assertEqual(response.status_code, 200)
        received_offers = response.json()
        
        print(f"  Received offers count: {len(received_offers)}")
        self.assertGreater(len(received_offers), 0, "Seller should see at least one received offer")
        
        received_offer_ids = [o['id'] for o in received_offers]
        self.assertIn(offer_id, received_offer_ids, "Offer should appear in Seller's 'Received' list")
        print(f"[OK] Offer {offer_id} found in Seller's 'Received' list")
        
        # Step 3: Verify Seller does NOT see offer in "Sent"
        print("\nSTEP 3: Seller checks 'Sent' offers")
        response = self.seller_client.get('/api/users/offers/sent/', **self.seller_headers)
        self.assertEqual(response.status_code, 200)
        sent_offers = response.json()
        
        print(f"  Sent offers count: {len(sent_offers)}")
        sent_offer_ids = [o['id'] for o in sent_offers]
        self.assertNotIn(offer_id, sent_offer_ids, "Offer should NOT appear in Seller's 'Sent' list")
        print(f"[OK] Offer {offer_id} correctly NOT in Seller's 'Sent' list")
        
        # Step 4: Verify Buyer sees offer in "Sent" (not Received)
        print("\nSTEP 4: Buyer checks 'Sent' offers")
        response = self.buyer_client.get('/api/users/offers/sent/', **self.buyer_headers)
        self.assertEqual(response.status_code, 200)
        sent_offers = response.json()
        
        print(f"  Sent offers count: {len(sent_offers)}")
        self.assertGreater(len(sent_offers), 0, "Buyer should see at least one sent offer")
        
        sent_offer_ids = [o['id'] for o in sent_offers]
        self.assertIn(offer_id, sent_offer_ids, "Offer should appear in Buyer's 'Sent' list")
        print(f"[OK] Offer {offer_id} found in Buyer's 'Sent' list")
        
        # Step 5: Verify Buyer does NOT see offer in "Received"
        print("\nSTEP 5: Buyer checks 'Received' offers")
        response = self.buyer_client.get('/api/users/offers/received/', **self.buyer_headers)
        self.assertEqual(response.status_code, 200)
        received_offers = response.json()
        
        print(f"  Received offers count: {len(received_offers)}")
        received_offer_ids = [o['id'] for o in received_offers]
        self.assertNotIn(offer_id, received_offer_ids, "Offer should NOT appear in Buyer's 'Received' list")
        print(f"[OK] Offer {offer_id} correctly NOT in Buyer's 'Received' list")
        
        # Final Summary
        print("\n" + "="*60)
        print("ALL TESTS PASSED - Offer Routing Logic is Correct!")
        print("="*60)
        print("\nSummary:")
        print("  - Seller sees offer in 'Received': OK")
        print("  - Seller does NOT see offer in 'Sent': OK")
        print("  - Buyer sees offer in 'Sent': OK")
        print("  - Buyer does NOT see offer in 'Received': OK")
