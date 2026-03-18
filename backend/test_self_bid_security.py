"""
Security Test: Prevent Self-Bidding
Run with: python manage.py test test_self_bid_security
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


class SelfBidSecurityTest(TestCase):
    """Test that users cannot make offers on their own tickets"""
    
    def setUp(self):
        """Set up test user and ticket"""
        # Create seller
        self.seller = User.objects.create_user(
            username='seller_security_test',
            email='seller@security.com',
            password='testpass123',
            role='seller'
        )
        
        # Create event and ticket
        artist = Artist.objects.create(name='Security Test Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Security Test Event',
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
        
        # Create client with seller authentication
        self.seller_client = Client()
        seller_token = str(RefreshToken.for_user(self.seller).access_token)
        self.seller_headers = {'HTTP_AUTHORIZATION': f'Bearer {seller_token}'}
    
    def test_seller_cannot_bid_on_own_ticket(self):
        """Test that seller cannot make offer on their own ticket"""
        print("\n" + "="*60)
        print("SECURITY TEST: Prevent Self-Bidding")
        print("="*60)
        
        # Attempt to make offer on own ticket
        print("\nSTEP 1: Seller attempts to make offer on own ticket")
        response = self.seller_client.post(
            '/api/users/offers/',
            data=json.dumps({
                'ticket': self.ticket.id,
                'amount': '150.00'
            }),
            content_type='application/json',
            **self.seller_headers
        )
        
        print(f"Response Status: {response.status_code}")
        
        # Should be rejected with 400 Bad Request
        self.assertEqual(response.status_code, 400, 
                        f"Expected 400, got {response.status_code}. Response: {response.content.decode()}")
        
        response_data = response.json()
        self.assertIn('ticket', response_data, "Error should mention 'ticket' field")
        self.assertIn('own ticket', str(response_data).lower(), 
                     "Error message should mention 'own ticket'")
        
        print("[OK] Backend correctly rejected self-bid attempt")
        
        # Verify no offer was created
        offers_count = Offer.objects.filter(ticket=self.ticket, buyer=self.seller).count()
        self.assertEqual(offers_count, 0, "No offer should be created for self-bid")
        print("[OK] No offer was created in database")
        
        print("\n" + "="*60)
        print("SECURITY TEST PASSED - Self-bidding prevented!")
        print("="*60)
