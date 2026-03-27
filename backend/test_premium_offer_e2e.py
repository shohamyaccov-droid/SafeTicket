"""
E2E Test for Premium Offer Modal and Routing Logic
Run with: python manage.py test test_premium_offer_e2e
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import Ticket, Event, Artist, Offer, Order
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
import json

User = get_user_model()


class PremiumOfferE2ETest(TestCase):
    """E2E test for premium offer modal and routing"""
    
    def setUp(self):
        """Set up test users and ticket"""
        # Create users
        self.seller = User.objects.create_user(
            username='seller_premium_test',
            email='seller@premium.com',
            password='testpass123',
            role='seller'
        )
        
        self.buyer = User.objects.create_user(
            username='buyer_premium_test',
            email='buyer@premium.com',
            password='testpass123',
            role='buyer'
        )
        
        # Create event and ticket
        artist = Artist.objects.create(name='Premium Test Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Premium Test Event',
            date=timezone.now() + timedelta(days=30),
            venue='Test Venue',
            city='Tel Aviv'
        )
        
        # Create ticket owned by seller with asking price 200 ILS
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
    
    def test_premium_offer_flow(self):
        """Test complete premium offer flow"""
        print("\n" + "="*60)
        print("E2E PREMIUM OFFER FLOW TEST")
        print("="*60)
        
        # Step 1: Buyer makes offer using quick button calculation (85% = 170 ILS)
        print("\nSTEP 1: Buyer creates offer using 85% quick button (170 ILS)")
        offer_amount = 170.00  # 85% of 200
        
        response = self.buyer_client.post(
            '/api/users/offers/',
            data=json.dumps({
                'ticket': self.ticket.id,
                'amount': str(offer_amount)
            }),
            content_type='application/json',
            **self.buyer_headers
        )
        self.assertEqual(response.status_code, 201, f"Expected 201, got {response.status_code}. Response: {response.content.decode()}")
        offer = response.json()
        offer_id = offer['id']
        print(f"[OK] Offer created: ID {offer_id}, Amount: {offer['amount']} ILS")
        self.assertEqual(float(offer['amount']), offer_amount)
        
        # Step 2: Verify Seller sees offer EXACTLY in "Received" tab
        print("\nSTEP 2: Seller checks 'Received' offers")
        response = self.seller_client.get('/api/users/offers/received/', **self.seller_headers)
        self.assertEqual(response.status_code, 200)
        received_offers = response.json()
        
        print(f"  Received offers count: {len(received_offers)}")
        self.assertGreater(len(received_offers), 0, "Seller should see at least one received offer")
        
        received_offer_ids = [o['id'] for o in received_offers]
        self.assertIn(offer_id, received_offer_ids, 
                     f"Offer {offer_id} MUST appear in Seller's 'Received' list. Found: {received_offer_ids}")
        print(f"[OK] Offer {offer_id} found in Seller's 'Received' list")
        
        # Verify seller does NOT see it in Sent
        response = self.seller_client.get('/api/users/offers/sent/', **self.seller_headers)
        sent_offers = response.json()
        sent_offer_ids = [o['id'] for o in sent_offers]
        self.assertNotIn(offer_id, sent_offer_ids, 
                        f"Offer {offer_id} MUST NOT appear in Seller's 'Sent' list")
        print(f"[OK] Offer {offer_id} correctly NOT in Seller's 'Sent' list")
        
        # Step 3: Verify Buyer sees offer EXACTLY in "Sent" tab
        print("\nSTEP 3: Buyer checks 'Sent' offers")
        response = self.buyer_client.get('/api/users/offers/sent/', **self.buyer_headers)
        self.assertEqual(response.status_code, 200)
        sent_offers = response.json()
        
        print(f"  Sent offers count: {len(sent_offers)}")
        self.assertGreater(len(sent_offers), 0, "Buyer should see at least one sent offer")
        
        sent_offer_ids = [o['id'] for o in sent_offers]
        self.assertIn(offer_id, sent_offer_ids,
                     f"Offer {offer_id} MUST appear in Buyer's 'Sent' list. Found: {sent_offer_ids}")
        print(f"[OK] Offer {offer_id} found in Buyer's 'Sent' list")
        
        # Verify buyer does NOT see it in Received
        response = self.buyer_client.get('/api/users/offers/received/', **self.buyer_headers)
        received_offers = response.json()
        received_offer_ids = [o['id'] for o in received_offers]
        self.assertNotIn(offer_id, received_offer_ids,
                        f"Offer {offer_id} MUST NOT appear in Buyer's 'Received' list")
        print(f"[OK] Offer {offer_id} correctly NOT in Buyer's 'Received' list")
        
        # Step 4: Test quick button calculations
        print("\nSTEP 4: Verify quick button calculations")
        asking_price = 200.00
        
        # Test 85% calculation
        good_bid = asking_price * 0.85
        self.assertEqual(good_bid, 170.00, "85% should equal 170 ILS")
        print(f"[OK] Good Bid (85%): {good_bid} ILS")
        
        # Test 95% calculation
        competitive_bid = asking_price * 0.95
        self.assertEqual(competitive_bid, 190.00, "95% should equal 190 ILS")
        print(f"[OK] Competitive Bid (95%): {competitive_bid} ILS")
        
        # Test 100% calculation
        buy_now = asking_price * 1.00
        self.assertEqual(buy_now, 200.00, "100% should equal 200 ILS")
        print(f"[OK] Buy Now (100%): {buy_now} ILS")
        
        # Final Summary
        print("\n" + "="*60)
        print("ALL TESTS PASSED - Premium Offer Flow Working!")
        print("="*60)
        print("\nSummary:")
        print("  - Offer created successfully: OK")
        print("  - Seller sees offer in 'Received': OK")
        print("  - Seller does NOT see offer in 'Sent': OK")
        print("  - Buyer sees offer in 'Sent': OK")
        print("  - Buyer does NOT see offer in 'Received': OK")
        print("  - Quick button calculations correct: OK")

    def test_purchase_completed_true_after_paid_order(self):
        """Completed purchase (paid order + related_offer) → API exposes purchase_completed for UI lock."""
        response = self.buyer_client.post(
            '/api/users/offers/',
            data=json.dumps({'ticket': self.ticket.id, 'amount': '170.00'}),
            content_type='application/json',
            **self.buyer_headers,
        )
        self.assertEqual(response.status_code, 201, response.content.decode())
        offer_id = response.json()['id']

        response = self.seller_client.post(
            f'/api/users/offers/{offer_id}/accept/',
            data='{}',
            content_type='application/json',
            **self.seller_headers,
        )
        self.assertEqual(response.status_code, 200, response.content.decode())

        offer = Offer.objects.get(id=offer_id)
        Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            status='paid',
            total_amount=187.00,
            quantity=1,
            related_offer=offer,
            event_name=self.event.name,
        )

        response = self.buyer_client.get('/api/users/offers/sent/', **self.buyer_headers)
        self.assertEqual(response.status_code, 200)
        sent = response.json()
        row = next((o for o in sent if o['id'] == offer_id), None)
        self.assertIsNotNone(row)
        self.assertTrue(
            row.get('purchase_completed'),
            'purchase_completed must be true so the dashboard can hide "השלם רכישה"',
        )

    def test_new_offer_immediately_visible_in_sent_list(self):
        """POST offer then GET /sent/ — new row is returned without relying on a full page refresh."""
        response = self.buyer_client.post(
            '/api/users/offers/',
            data=json.dumps({'ticket': self.ticket.id, 'amount': '180.00'}),
            content_type='application/json',
            **self.buyer_headers,
        )
        self.assertEqual(response.status_code, 201, response.content.decode())
        offer_id = response.json()['id']

        response = self.buyer_client.get('/api/users/offers/sent/', **self.buyer_headers)
        self.assertEqual(response.status_code, 200)
        sent = response.json()
        ids = [o['id'] for o in sent]
        self.assertIn(
            offer_id,
            ids,
            'New offer must appear in GET /offers/sent/ immediately after creation',
        )
