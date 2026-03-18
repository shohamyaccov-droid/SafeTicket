"""
E2E QA: Email Verification (OTP) and Automated Notifications
Rigorous tests using django.core.mail.outbox to prove:
  - Test 1: Fake account block - unverified users cannot login (401)
  - Test 2: OTP verification - extract OTP from outbox, verify, login succeeds
  - Test 3: PDF delivery - purchase flow sends receipt email with PDF attachment

Run: python manage.py test test_e2e_email_otp -v 2
"""
import math
import re
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework_simplejwt.tokens import RefreshToken
from users.models import Ticket, Event, Artist, Order
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class E2EEmailOTPTest(TestCase):
    """E2E tests for OTP flow and automated emails."""

    def setUp(self):
        mail.outbox.clear()

    def test_1_fake_account_block(self):
        """
        Register a user. Attempt to log in WITHOUT verifying.
        Assert login strictly fails with 401.
        """
        # Register
        r1 = self.client.post('/api/users/register/', {
            'username': 'unverified_user',
            'email': 'unverified@test.com',
            'password': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'role': 'buyer',
        }, format='json')
        self.assertEqual(r1.status_code, 201, r1.content.decode())
        self.assertNotIn('access', r1.json())

        # OTP email was sent
        self.assertEqual(len(mail.outbox), 1, 'OTP email should be sent')
        self.assertIn('unverified@test.com', mail.outbox[0].to)

        # Login WITHOUT verifying - must fail with 401
        r2 = self.client.post('/api/users/login/', {
            'username': 'unverified_user',
            'password': 'SecurePass123!',
        }, format='json')
        self.assertIn(r2.status_code, (401, 403), f'Expected 401/403, got {r2.status_code}. Body: {r2.content.decode()}')
        data = r2.json()
        self.assertIn('detail', data)
        detail_lower = str(data.get('detail', '')).lower()
        self.assertTrue(
            'email_not_verified' in detail_lower or ('email' in detail_lower and 'verif' in detail_lower),
            f'Expected email verification error, got: {data}'
        )

    def test_2_otp_verification_and_login(self):
        """
        Register, extract OTP from mail.outbox, verify, then login succeeds.
        """
        # Register
        r1 = self.client.post('/api/users/register/', {
            'username': 'verify_me',
            'email': 'verify_me@test.com',
            'password': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'role': 'buyer',
        }, format='json')
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)

        # Extract 6-digit OTP from email body
        body = mail.outbox[0].body
        match = re.search(r'\b(\d{6})\b', body)
        self.assertIsNotNone(match, f'No 6-digit OTP found in email body: {body[:200]}')
        otp = match.group(1)

        # Verify email
        r2 = self.client.post('/api/users/verify-email/', {
            'email': 'verify_me@test.com',
            'otp': otp,
        }, format='json')
        self.assertEqual(r2.status_code, 200, r2.content.decode())
        self.assertIn('access', r2.json())
        self.assertIn('refresh', r2.json())

        # Login now succeeds
        r3 = self.client.post('/api/users/login/', {
            'username': 'verify_me',
            'password': 'SecurePass123!',
        }, format='json')
        self.assertEqual(r3.status_code, 200, r3.content.decode())
        self.assertIn('access', r3.json())

    def test_3_pdf_receipt_delivery(self):
        """
        Simulate user buying a ticket. Assert:
        - mail.outbox length increases
        - Sent email has PDF attachment
        - Recipient matches buyer
        """
        # Create verified seller and buyer (bypass OTP for this test)
        seller = User.objects.create_user(
            username='pdf_seller',
            email='pdf_seller@test.com',
            password='testpass123',
            role='seller',
            is_email_verified=True,
        )
        buyer = User.objects.create_user(
            username='pdf_buyer',
            email='pdf_buyer@test.com',
            password='testpass123',
            role='buyer',
            is_email_verified=True,
        )

        # Create event and ticket with PDF
        artist = Artist.objects.create(name='PDF Test Artist')
        event = Event.objects.create(
            artist=artist,
            name='PDF Test Event',
            date=timezone.now() + timedelta(days=30),
            venue='מנורה מבטחים',
            city='Tel Aviv',
        )
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
        pdf_file = SimpleUploadedFile('ticket.pdf', pdf_content, content_type='application/pdf')
        ticket = Ticket.objects.create(
            seller=seller,
            event=event,
            event_name='PDF Test Event',
            original_price=100.00,
            asking_price=100.00,
            pdf_file=pdf_file,
            status='active',
            available_quantity=1,
            verification_status='מאומת',
        )

        outbox_before = len(mail.outbox)

        # Simulate payment then create order (authenticated buyer)
        token = str(RefreshToken.for_user(buyer).access_token)
        expected_total = math.ceil(float(ticket.asking_price) * 1.10) * 1
        pay_r = self.client.post(
            '/api/users/payments/simulate/',
            {'ticket_id': ticket.id, 'amount': expected_total, 'quantity': 1},
            format='json',
        )
        self.assertEqual(pay_r.status_code, 200)

        order_r = self.client.post(
            '/api/users/orders/',
            {
                'ticket': ticket.id,
                'total_amount': int(expected_total),
                'quantity': 1,
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(order_r.status_code, 201, order_r.content.decode())

        # Assert mail.outbox increased
        self.assertGreater(len(mail.outbox), outbox_before, 'Receipt email should be sent')
        receipt_emails = [m for m in mail.outbox if 'Receipt' in (m.subject or '')]
        self.assertGreater(len(receipt_emails), 0, 'At least one receipt email')

        # Assert recipient matches buyer
        last_receipt = receipt_emails[-1]
        self.assertIn(buyer.email, last_receipt.to, f'Recipient should be {buyer.email}, got {last_receipt.to}')

        # Assert PDF is attached
        self.assertGreater(len(last_receipt.attachments), 0, 'Receipt email must have PDF attachment')
        has_pdf = False
        for att in last_receipt.attachments:
            fn = att[0] if len(att) >= 1 else None
            content = att[1] if len(att) >= 2 else b''
            if fn and str(fn).lower().endswith('.pdf'):
                has_pdf = True
                break
            if isinstance(content, bytes) and content[:4] == b'%PDF':
                has_pdf = True
                break
        self.assertTrue(has_pdf, f'No PDF attachment found. Attachments: {last_receipt.attachments}')
