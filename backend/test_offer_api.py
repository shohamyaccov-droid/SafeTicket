"""
Quick test script to verify Offer API endpoint works
Run with: python manage.py test test_offer_api (inside venv)
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import Ticket, Event, Artist
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
import json

User = get_user_model()


class OfferAPITest(TestCase):
    """Test Offer API endpoint"""
    
    def setUp(self):
        """Set up test data"""
        # Create test users
        self.seller = User.objects.create_user(
            username='test_seller_offer',
            email='seller@test.com',
            password='testpass123',
            role='seller'
        )
        
        self.buyer = User.objects.create_user(
            username='test_buyer_offer',
            email='buyer@test.com',
            password='testpass123',
            role='buyer'
        )
        
        # Create event and ticket
        artist = Artist.objects.create(name='Test Artist Offer')
        event = Event.objects.create(
            artist=artist,
            name='Test Event Offer',
            date=timezone.now() + timedelta(days=30),
            venue='Test Venue',
            city='Tel Aviv'
        )
        
        # Create ticket
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
        pdf_file = SimpleUploadedFile('test_ticket.pdf', pdf_content, content_type='application/pdf')
        
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            original_price=200.00,
            asking_price=200.00,
            pdf_file=pdf_file,
            status='active',
            available_quantity=1
        )
    
    def test_offer_creation(self):
        """Test creating an offer via API"""
        print("\n" + "="*60)
        print("Testing Offer API Endpoint")
        print("="*60)
        
        print(f"\n[OK] Created test ticket ID: {self.ticket.id}")
        print(f"[OK] Ticket price: {self.ticket.asking_price} ILS")
        
        # Get token
        buyer_token = str(RefreshToken.for_user(self.buyer).access_token)
        
        print(f"\n[SEND] Sending POST request to /api/users/offers/")
        print(f"   Ticket ID: {self.ticket.id}")
        print(f"   Offer Amount: 150.00 ILS")
        
        response = self.client.post(
            '/api/users/offers/',
            data=json.dumps({
                'ticket': self.ticket.id,
                'amount': '150.00'
            }),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {buyer_token}'
        )
        
        print(f"\n[RESPONSE] Status: {response.status_code}")
        
        self.assertEqual(response.status_code, 201, f"Expected 201, got {response.status_code}. Response: {response.content.decode()}")
        
        offer_data = response.json()
        print("[SUCCESS] Offer created successfully!")
        print(f"\nOffer Details:")
        print(f"  - Offer ID: {offer_data['id']}")
        print(f"  - Amount: {offer_data['amount']} ILS")
        print(f"  - Status: {offer_data['status']}")
        print(f"  - Expires at: {offer_data['expires_at']}")
        print(f"  - Buyer: {offer_data['buyer_username']}")
        
        # Verify offer data
        self.assertEqual(offer_data['status'], 'pending')
        self.assertEqual(float(offer_data['amount']), 150.00)
        self.assertIsNotNone(offer_data['expires_at'])
        self.assertEqual(offer_data['buyer_username'], 'test_buyer_offer')
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED - Offer API is working correctly!")
        print("="*60)
