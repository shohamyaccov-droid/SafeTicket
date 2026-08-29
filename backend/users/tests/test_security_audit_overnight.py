"""
Overnight security audit — defensive tests (no exploit payloads).

Asserts that forged payments, disguised uploads, IDOR downloads, PII scraping,
and contact-field bypasses are rejected by the API.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from pypdf import PdfWriter
from rest_framework.test import APIClient, APIRequestFactory

from users.models import Artist, Event, Order, SellerPayout, Ticket
from users.payme_views import payme_webhook
from users.payout_ledger import ensure_seller_payout_for_order
from users.pricing import expected_buy_now_total
from users.tests.payme_ipn_test_helpers import MOCK_PAYME_SALE_NOT_FOUND

User = get_user_model()
UPLOAD_URL = '/api/users/tickets/'


def _valid_pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _pdf_upload(name='ticket.pdf'):
    return SimpleUploadedFile(name, _valid_pdf_bytes(), content_type='application/pdf')


def _disguised_script(name='ticket.pdf', content_type='application/pdf'):
    return SimpleUploadedFile(
        name,
        b'<html><script>document.cookie</script></html>',
        content_type=content_type,
    )


@override_settings(DEBUG=False, SECRET_KEY='overnight-security-secret', RELAX_PDF_UPLOAD_VALIDATION=True)
class UploadAndReceiptHardeningTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.seller = User.objects.create_user(
            username='sec_upload_seller',
            email='sec_upload_seller@example.test',
            password='ValidPass123!',
            role='seller',
            phone_number='0501112233',
        )
        self.artist = Artist.objects.create(name='Sec Upload Artist')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Sec Upload Event',
            date=timezone.now() + timedelta(days=20),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='US',
            category='concert',
        )
        self.api.force_authenticate(self.seller)

    def _payload(self, ticket_file, receipt_file=None):
        data = {
            'event_id': str(self.event.id),
            'original_price': '90.00',
            'listing_price': '90.00',
            'available_quantity': '1',
            'pdf_files_count': '1',
            'il_legal_declaration': 'true',
            'pdf_file_0': ticket_file,
        }
        if receipt_file is not None:
            data['receipt_file'] = receipt_file
        return data

    def test_script_disguised_as_pdf_is_rejected(self):
        res = self.api.post(UPLOAD_URL, self._payload(_disguised_script()), format='multipart')
        self.assertEqual(res.status_code, 400, res.content)
        self.assertFalse(Ticket.objects.filter(seller=self.seller).exists())

    def test_relax_flag_ignored_outside_debug(self):
        spoofed = SimpleUploadedFile(
            'ticket.pdf',
            b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n',
            content_type='text/plain',
        )
        res = self.api.post(UPLOAD_URL, self._payload(spoofed), format='multipart')
        self.assertEqual(res.status_code, 400, res.content)

    def test_html_receipt_is_rejected(self):
        res = self.api.post(
            UPLOAD_URL,
            self._payload(
                _pdf_upload(),
                receipt_file=_disguised_script(name='receipt.pdf'),
            ),
            format='multipart',
        )
        self.assertEqual(res.status_code, 400, res.content)
        self.assertFalse(Ticket.objects.filter(seller=self.seller).exists())

    def test_anonymous_cannot_upload_ticket(self):
        self.api.force_authenticate(user=None)
        res = self.api.post(UPLOAD_URL, self._payload(_pdf_upload()), format='multipart')
        self.assertIn(res.status_code, (401, 403))


@override_settings(DEBUG=False, SECRET_KEY='overnight-security-secret')
class PublicTicketPiiAndIdorTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.seller = User.objects.create_user(
            username='sec_pii_seller',
            email='sec_pii_seller@example.test',
            password='ValidPass123!',
            role='seller',
            phone_number='0502223344',
            payout_details='{"account_number":"999888777"}',
        )
        self.other = User.objects.create_user(
            username='sec_pii_other',
            email='sec_pii_other@example.test',
            password='ValidPass123!',
            phone_number='0503334455',
        )
        artist = Artist.objects.create(name='Sec PII Artist')
        event = Event.objects.create(
            artist=artist,
            name='Sec PII Event',
            date=timezone.now() + timedelta(days=12),
            venue='בלומפילד',
            city='Tel Aviv',
            country='US',
            category='concert',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            event_name=event.name,
            event_date=event.date,
            venue=event.venue,
            original_price=Decimal('150.00'),
            asking_price=Decimal('150.00'),
            status='active',
            available_quantity=1,
            reservation_email='hidden-guest@example.test',
            pdf_file=_pdf_upload(),
        )

    def test_public_ticket_detail_strips_reservation_pii(self):
        res = self.api.get(f'/api/users/tickets/{self.ticket.pk}/')
        self.assertEqual(res.status_code, 200, res.content)
        body = res.json()
        self.assertNotIn('reservation_email', body)
        self.assertNotIn('reserved_by', body)
        self.assertIsNone(body.get('pdf_file_url'))
        blob = str(body).lower()
        self.assertNotIn('hidden-guest@example.test', blob)
        self.assertNotIn('999888777', blob)
        self.assertNotIn('sec_pii_seller@example.test', blob)
        self.assertNotIn('0502223344', blob)

    def test_public_ticket_list_has_no_seller_pii(self):
        res = self.api.get('/api/users/tickets/')
        self.assertEqual(res.status_code, 200, res.content)
        blob = str(res.json()).lower()
        self.assertNotIn('sec_pii_seller@example.test', blob)
        self.assertNotIn('0502223344', blob)
        self.assertNotIn('payout_details', blob)
        self.assertNotIn('account_number', blob)

    def test_other_user_download_returns_no_file_bytes(self):
        self.api.force_authenticate(self.other)
        res = self.api.get(f'/api/users/tickets/{self.ticket.pk}/download_pdf/')
        self.assertEqual(res.status_code, 403)
        self.assertFalse(res.content.startswith(b'%PDF'))
        self.assertNotIn(b'%PDF', res.content[:64])

    def test_other_user_cannot_download_receipt(self):
        self.api.force_authenticate(self.other)
        res = self.api.get(f'/api/users/tickets/{self.ticket.pk}/download_receipt/')
        self.assertEqual(res.status_code, 403)
        self.assertFalse(res.content.startswith(b'%PDF'))

    def test_profile_returns_only_authenticated_user(self):
        self.api.force_authenticate(self.other)
        res = self.api.get('/api/users/profile/')
        self.assertEqual(res.status_code, 200, res.content)
        body = res.json()
        user = body.get('user') or body
        self.assertEqual(user.get('email'), 'sec_pii_other@example.test')
        self.assertNotEqual(user.get('email'), 'sec_pii_seller@example.test')
        self.assertNotIn('999888777', str(body))


@override_settings(DEBUG=False, SECRET_KEY='overnight-security-secret')
class CheckoutAndEscrowGateTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.seller = User.objects.create_user(
            username='sec_pay_seller',
            email='sec_pay_seller@example.test',
            password='ValidPass123!',
            role='seller',
            phone_number='0504445566',
        )
        self.buyer = User.objects.create_user(
            username='sec_pay_buyer',
            email='sec_pay_buyer@example.test',
            password='ValidPass123!',
            role='buyer',
            first_name='Buyer',
            phone_number='0505556677',
        )
        artist = Artist.objects.create(name='Sec Pay Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Sec Pay Event',
            date=timezone.now() + timedelta(days=18),
            venue='בלומפילד',
            city='Tel Aviv',
            country='US',
            category='concert',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            event_date=self.event.date,
            venue=self.event.venue,
            original_price=Decimal('200.00'),
            asking_price=Decimal('200.00'),
            status='active',
            available_quantity=1,
            verification_status='מאומת',
            pdf_file='tickets/pdfs/sec-pay.pdf',
        )
        self.expected = expected_buy_now_total(self.ticket.asking_price, 1)

    def test_underpay_does_not_create_pending_order(self):
        self.api.force_authenticate(self.buyer)
        self.api.post(f'/api/users/tickets/{self.ticket.pk}/reserve/', {}, format='json')
        under = (self.expected - Decimal('80.00')).quantize(Decimal('0.01'))
        res = self.api.post(
            '/api/users/orders/',
            {
                'ticket_id': self.ticket.pk,
                'quantity': 1,
                'total_amount': str(under),
                'accepted_terms': True,
            },
            format='json',
        )
        self.assertIn(res.status_code, (400, 403, 409), res.content)
        self.assertFalse(Order.objects.filter(ticket=self.ticket, total_amount=under).exists())

    def test_seller_cannot_mark_own_payout_paid(self):
        order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            status='paid',
            total_amount=self.expected,
            total_paid_by_buyer=self.expected,
            final_negotiated_price=Decimal('200.00'),
            buyer_service_fee=self.expected - Decimal('200.00'),
            seller_service_fee=Decimal('0.00'),
            net_seller_revenue=Decimal('200.00'),
            quantity=1,
            event_name=self.event.name,
            payout_status='eligible',
            payout_eligible_date=timezone.now() - timedelta(hours=1),
        )
        payout = ensure_seller_payout_for_order(order)
        self.assertIsNotNone(payout)
        self.api.force_authenticate(self.seller)
        res = self.api.post(f'/api/users/admin/payouts/{payout.pk}/mark-paid/', {}, format='json')
        self.assertEqual(res.status_code, 403)
        payout.refresh_from_db()
        self.assertNotEqual(payout.payout_status, SellerPayout.PayoutStatus.TRANSFERRED)

    def test_forged_payme_webhook_without_api_confirm_does_not_pay(self):
        order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            ticket_ids=[self.ticket.id],
            status='pending_payment',
            total_amount=self.expected,
            currency='ILS',
            quantity=1,
            payme_transaction_id='txn_forged_audit',
            payme_status='initialized',
        )
        payload = {
            'merchant_order_id': str(order.id),
            'transaction_id': 'txn_forged_audit',
            'sale_price': int(self.expected * 100),
            'currency': 'ILS',
            'status': 'authorized',
        }
        request = APIRequestFactory().post(
            '/api/payments/webhook/payme/',
            data=payload,
            format='json',
        )
        with patch(
            'users.payme_views.confirm_payme_sale_status',
            return_value=dict(MOCK_PAYME_SALE_NOT_FOUND),
        ):
            response = payme_webhook(request)
        self.assertNotEqual(getattr(response, 'data', {}).get('finalized'), True)
        order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(order.status, 'pending_payment')
        self.assertNotEqual(self.ticket.status, 'sold')
