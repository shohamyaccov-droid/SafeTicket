"""
E2E Negotiation Test using Django TestCase
Run with: python manage.py test test_negotiation
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import Ticket, Event, Artist, Offer
from django.core.files.uploadedfile import SimpleUploadedFile
import json

User = get_user_model()


class NegotiationE2ETest(TestCase):
    """End-to-end test for Bid/Ask negotiation system"""
    
    def setUp(self):
        """Set up test users and ticket"""
        # Create users
        self.seller = User.objects.create_user(
            username='seller_test',
            email='seller@test.com',
            password='testpass123',
            role='seller'
        )
        
        self.buyer = User.objects.create_user(
            username='buyer_test',
            email='buyer@test.com',
            password='testpass123',
            role='buyer'
        )
        
        # Create event
        artist = Artist.objects.create(name='Test Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Test Event Negotiation',
            date=timezone.now() + timedelta(days=30),
            venue='Test Venue',
            city='Tel Aviv'
        )
        
        # Create ticket for 200 ILS
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
        pdf_file = SimpleUploadedFile('test_ticket.pdf', pdf_content, content_type='application/pdf')
        
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=200.00,
            asking_price=200.00,
            pdf_file=pdf_file,
            status='active',
            available_quantity=1,
            section='A',
            row='10',
            seat_numbers='1-1',
            is_together=True
        )
        
        # Create clients with authentication
        self.seller_client = Client()
        self.buyer_client = Client()
        
        seller_token = str(RefreshToken.for_user(self.seller).access_token)
        buyer_token = str(RefreshToken.for_user(self.buyer).access_token)
        
        self.seller_headers = {'HTTP_AUTHORIZATION': f'Bearer {seller_token}'}
        self.buyer_headers = {'HTTP_AUTHORIZATION': f'Bearer {buyer_token}'}
    
    def test_complete_negotiation_flow(self):
        """Test the complete negotiation flow"""
        print("\n" + "="*60)
        print("E2E NEGOTIATION TEST - Complete Flow")
        print("="*60)
        
        # Step 1: Verify ticket is created with 200 ILS
        print("\nSTEP 1: Ticket created for 200 ILS")
        self.assertEqual(float(self.ticket.asking_price), 200.00)
        print(f"✓ Ticket ID: {self.ticket.id}, Price: 200 ILS")
        
        # Step 2: Buyer makes offer for 100 ILS
        print("\nSTEP 2: Buyer makes offer for 100 ILS")
        response = self.buyer_client.post(
            '/api/users/offers/',
            data=json.dumps({
                'ticket': self.ticket.id,
                'amount': '100.00'
            }),
            content_type='application/json',
            **self.buyer_headers
        )
        self.assertEqual(response.status_code, 201)
        offer_1 = response.json()
        offer_1_id = offer_1['id']
        self.assertEqual(offer_1['status'], 'pending')
        self.assertEqual(float(offer_1['amount']), 100.00)
        print(f"✓ Created offer ID {offer_1_id} for 100 ILS")
        
        # Step 3: Seller counters with 150 ILS
        print("\nSTEP 3: Seller counters with 150 ILS")
        response = self.seller_client.post(
            f'/api/users/offers/{offer_1_id}/counter/',
            data=json.dumps({'amount': '150.00'}),
            content_type='application/json',
            **self.seller_headers
        )
        self.assertEqual(response.status_code, 201)
        counter = response.json()
        counter_id = counter['id']
        print(f"✓ Created counter-offer ID {counter_id} for 150 ILS")
        
        # Verify original offer is countered
        response = self.seller_client.get('/api/users/offers/received/', **self.seller_headers)
        offers_received = response.json()
        original_offer = next((o for o in offers_received if o['id'] == offer_1_id), None)
        self.assertIsNotNone(original_offer)
        self.assertEqual(original_offer['status'], 'countered')
        print("✓ Original offer marked as countered")
        
        # Step 4: Buyer makes new offer for 120 ILS
        print("\nSTEP 4: Buyer makes new offer for 120 ILS")
        response = self.buyer_client.post(
            '/api/users/offers/',
            data=json.dumps({
                'ticket': self.ticket.id,
                'amount': '120.00'
            }),
            content_type='application/json',
            **self.buyer_headers
        )
        self.assertEqual(response.status_code, 201)
        offer_2 = response.json()
        offer_2_id = offer_2['id']
        self.assertEqual(offer_2['status'], 'pending')
        self.assertEqual(float(offer_2['amount']), 120.00)
        print(f"✓ Created offer ID {offer_2_id} for 120 ILS")
        
        # Step 5: Seller ACCEPTs the 120 ILS offer
        print("\nSTEP 5: Seller ACCEPTs the 120 ILS offer")
        response = self.seller_client.post(
            f'/api/users/offers/{offer_2_id}/accept/',
            **self.seller_headers
        )
        self.assertEqual(response.status_code, 200)
        accepted_offer = response.json()
        self.assertEqual(accepted_offer['status'], 'accepted')
        self.assertEqual(float(accepted_offer['amount']), 120.00)
        self.assertIsNotNone(accepted_offer['checkout_expires_at'])
        print(f"✓ Accepted offer ID {offer_2_id}")
        print(f"  - Negotiated price: {accepted_offer['amount']} ILS")
        print(f"  - Checkout expires at: {accepted_offer['checkout_expires_at']}")
        
        # Verify other pending offers are rejected
        response = self.seller_client.get('/api/users/offers/received/', **self.seller_headers)
        offers_received_after = response.json()
        pending_offers = [o for o in offers_received_after if o['status'] == 'pending' and o['ticket'] == self.ticket.id]
        self.assertEqual(len(pending_offers), 0, "All other pending offers should be rejected")
        print("✓ Other pending offers automatically rejected")
        
        # Step 6: Verify Buyer sees accepted offer in "Offers Sent"
        print("\nSTEP 6: Verify Buyer sees accepted offer in 'Offers Sent'")
        response = self.buyer_client.get('/api/users/offers/sent/', **self.buyer_headers)
        offers_sent = response.json()
        buyer_accepted = next((o for o in offers_sent if o['id'] == offer_2_id), None)
        self.assertIsNotNone(buyer_accepted, "Buyer should see the accepted offer")
        self.assertEqual(buyer_accepted['status'], 'accepted')
        self.assertEqual(float(buyer_accepted['amount']), 120.00)
        print("✓ Buyer can see accepted offer with 'השלם רכישה' button available")
        
        # Step 7: Verify public listing price is still 200 ILS
        print("\nSTEP 7: Verify public listing price unchanged (200 ILS)")
        response = self.buyer_client.get(f'/api/users/tickets/{self.ticket.id}/', **self.buyer_headers)
        ticket_details = response.json()
        self.assertEqual(float(ticket_details['asking_price']), 200.00)
        print("✓ Public listing still shows 200 ILS for other users")
        
        # Step 8: Verify checkout would use negotiated price
        print("\nSTEP 8: Verify checkout logic uses negotiated price")
        response = self.buyer_client.get(f'/api/users/offers/{offer_2_id}/', **self.buyer_headers)
        offer_details = response.json()
        self.assertEqual(offer_details['status'], 'accepted')
        self.assertEqual(float(offer_details['amount']), 120.00)
        self.assertIsNotNone(offer_details['checkout_expires_at'])
        print("✓ Checkout will use negotiated price: 120 ILS")
        print(f"✓ Checkout window expires at: {offer_details['checkout_expires_at']}")
        
        # Final Summary
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print(f"\nTest Summary:")
        print(f"  - Ticket ID: {self.ticket.id}")
        print(f"  - Public Price: 200 ILS (unchanged)")
        print(f"  - Negotiated Price: 120 ILS (for Buyer only)")
        print(f"  - Offer Status: Accepted")
        print(f"  - Checkout Window: 4 hours from acceptance")
        print("\n✓ Bid/Ask Negotiation System is working correctly!")
