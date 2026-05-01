"""
E2E QA: Registration, optional OTP verify endpoint, and receipt email after purchase.

Current product behavior (OTP sending dormant on register — see RegisterView):
  - Registration returns JWT immediately (instant login / seamless onboarding).
  - /api/users/verify-email/ still works when OTP is seeded in cache (e.g. future OTP flow).

Run:
  python manage.py test test_e2e_email_otp -v 2
"""
from decimal import Decimal
import base64
import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import Ticket, Event, Artist
from users.pricing import expected_buy_now_total

User = get_user_model()


class E2EEmailOTPTest(TransactionTestCase):
    """Auth + receipt path tests aligned with production registration (instant JWT)."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.enforce_csrf_checks = False

    def test_1_seamless_registration_returns_jwt_and_login_works(self):
        """
        Register: expect 201 + access/refresh (no waiting for OTP mail).
        Login with same credentials succeeds.
        """
        r1 = self.client.post(
            '/api/users/register/',
            {
                'username': 'instant_user',
                'email': 'instant@test.com',
                'password': 'SecurePass123!',
                'password2': 'SecurePass123!',
                'role': 'buyer',
            },
            format='json',
        )
        self.assertEqual(r1.status_code, 201, r1.content.decode())
        data = r1.json()
        self.assertIn('access', data)
        self.assertIn('refresh', data)
        self.assertTrue(data.get('user', {}).get('is_email_verified', False))

        r2 = self.client.post(
            '/api/users/login/',
            {
                'username': 'instant_user',
                'password': 'SecurePass123!',
            },
            format='json',
        )
        self.assertEqual(r2.status_code, 200, r2.content.decode())
        self.assertIn('access', r2.json())

    def test_2_verify_email_with_cached_otp_returns_tokens(self):
        """
        OTP email is not sent on register while flow is dormant — seed cache and hit verify-email.
        """
        User.objects.create_user(
            username='verify_me',
            email='verify_me@test.com',
            password='SecurePass123!',
            role='buyer',
            is_email_verified=False,
        )
        cache.set('otp:verify_me@test.com', '123456', timeout=600)

        r2 = self.client.post(
            '/api/users/verify-email/',
            {
                'email': 'verify_me@test.com',
                'otp': '123456',
            },
            format='json',
        )
        self.assertEqual(r2.status_code, 200, r2.content.decode())
        self.assertIn('access', r2.json())
        self.assertIn('refresh', r2.json())

        user = User.objects.get(email='verify_me@test.com')
        self.assertTrue(user.is_email_verified)

    @mock.patch.dict('os.environ', {'RESEND_API_KEY': 're_test_key'})
    @mock.patch('users.utils.emails.resend.Emails.send', return_value={'id': 'email_test'})
    def test_3_pdf_receipt_delivery(self, mock_resend_send):
        """
        Buy-now flow: payment simulate + order; receipt mail with attachment.

        Uses pricing.expected_buy_now_total — NOT math.ceil(float * 1.1) (float gives 111 vs 110).
        """
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

        artist = Artist.objects.create(name='PDF Test Artist')
        event = Event.objects.create(
            artist=artist,
            name='PDF Test Event',
            date=timezone.now() + timedelta(days=30),
            venue='מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
        )
        pdf_content = (
            b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
        )
        pdf_file = SimpleUploadedFile('ticket.pdf', pdf_content, content_type='application/pdf')
        ticket = Ticket.objects.create(
            seller=seller,
            event=event,
            event_name='PDF Test Event',
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            pdf_file=pdf_file,
            status='active',
            available_quantity=1,
            verification_status='מאומת',
        )
        ticket.refresh_from_db()

        token = str(RefreshToken.for_user(buyer).access_token)
        expected_total_dec = expected_buy_now_total(ticket.asking_price, 1)
        pay_r = self.client.post(
            '/api/users/payments/simulate/',
            {
                'ticket_id': ticket.id,
                'amount': str(expected_total_dec),
                'quantity': 1,
            },
            format='json',
        )
        self.assertEqual(pay_r.status_code, 200, pay_r.content.decode())

        order_r = self.client.post(
            '/api/users/orders/',
            {
                'ticket': ticket.id,
                'total_amount': str(expected_total_dec),
                'quantity': 1,
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(order_r.status_code, 201, order_r.content.decode())
        order_body = order_r.json()
        order_id = order_body['id']
        pay_tok = order_body.get('payment_confirm_token')
        self.assertTrue(pay_tok, 'Order should include payment_confirm_token while pending_payment')

        conf = self.client.post(
            f'/api/users/orders/{order_id}/confirm-payment/',
            {
                'mock_payment_ack': True,
                'payment_confirm_token': pay_tok,
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(conf.status_code, 200, conf.content.decode())

        receipt_payloads = []
        for _ in range(20):
            receipt_payloads = [
                call.args[0]
                for call in mock_resend_send.call_args_list
                if buyer.email in (call.args[0].get('to') or [])
                and ('קבלה' in (call.args[0].get('subject') or '') or 'Receipt' in (call.args[0].get('subject') or ''))
            ]
            if receipt_payloads:
                break
            time.sleep(0.1)

        self.assertGreater(len(receipt_payloads), 0, 'At least one receipt email to buyer')

        last_receipt = receipt_payloads[-1]
        self.assertEqual(last_receipt['from'], 'TradeTix <onboarding@resend.dev>')
        self.assertIn(buyer.email, last_receipt['to'])
        self.assertIn('html', last_receipt)
        self.assertIn('קבלה', last_receipt['subject'])

        attachments = last_receipt.get('attachments') or []
        self.assertGreater(len(attachments), 0, 'Receipt email must have PDF attachment')
        has_pdf = False
        for att in attachments:
            fn = att.get('filename')
            content = base64.b64decode(att.get('content') or '')
            if fn and str(fn).lower().endswith('.pdf'):
                has_pdf = True
                break
            if content[:4] == b'%PDF':
                has_pdf = True
                break
        self.assertTrue(has_pdf, f'No PDF attachment found. Attachments: {attachments}')
