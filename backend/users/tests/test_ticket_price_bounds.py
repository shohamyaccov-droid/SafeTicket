"""Reject non-positive listing / face prices on ticket create; preserve typed sell price."""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from pypdf import PdfWriter
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket

User = get_user_model()


def _blank_pdf(name='t.pdf'):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return SimpleUploadedFile(name, buf.getvalue(), content_type='application/pdf')


class TicketPriceBoundsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='price_seller',
            email='price_seller@example.test',
            password='SafePass123!',
            role='seller',
        )
        self.client.force_authenticate(user=self.seller)
        artist = Artist.objects.create(name='Price Bound Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Price Bound Show',
            date=timezone.now() + timedelta(days=40),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            country='IL',
            category='concert',
            status='פעיל',
        )

    def _pdf(self, name='t.pdf'):
        return SimpleUploadedFile(
            name,
            b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n',
            content_type='application/pdf',
        )

    def test_negative_listing_price_rejected(self):
        res = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '-10',
                'listing_price': '-10',
                'available_quantity': 1,
                'pdf_files_count': 1,
                'pdf_file_0': self._pdf(),
                'il_legal_declaration': 'true',
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, 400)

    def test_zero_listing_price_rejected(self):
        res = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '0',
                'listing_price': '0',
                'available_quantity': 1,
                'pdf_files_count': 1,
                'pdf_file_0': self._pdf('z.pdf'),
                'il_legal_declaration': 'true',
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, 400)


class SingleSellPriceIntegrityTests(TestCase):
    """Sell UI sends one price; it must be stored exactly on original + asking."""

    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='single_price_seller',
            email='single_price_seller@example.test',
            password='SafePass123!',
            role='seller',
        )
        self.client.force_authenticate(user=self.seller)
        artist = Artist.objects.create(name='Single Price Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Single Price Show',
            date=timezone.now() + timedelta(days=20),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            country='IL',
            category='concert',
            status='פעיל',
        )

    def _create(self, price, *, listing=None, original=None, qty=1):
        """Mimic Sell.jsx: listing_price + original_price both set to the typed amount."""
        sell = str(price)
        data = {
            'event_id': self.event.id,
            'original_price': sell if original is None else str(original),
            'listing_price': sell if listing is None else str(listing),
            'available_quantity': str(qty),
            'pdf_files_count': '1',
            'pdf_file_0': _blank_pdf(f'p{price}.pdf'),
            'il_legal_declaration': 'true',
            'delivery_method': 'instant',
        }
        return self.client.post('/api/users/tickets/', data, format='multipart')

    def test_small_prices_saved_exactly(self):
        for amount in (1, 2, 10):
            with self.subTest(amount=amount):
                res = self._create(amount)
                self.assertEqual(res.status_code, 201, getattr(res, 'data', res.content))
                ticket = Ticket.objects.get(pk=res.data['id'])
                expected = Decimal(amount)
                self.assertEqual(ticket.original_price, expected)
                self.assertEqual(ticket.asking_price, expected)
                self.assertEqual(res.data.get('asking_price'), amount)
                self.assertEqual(res.data.get('original_price'), amount)

    def test_listing_only_payload_sets_both_columns(self):
        res = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'listing_price': '10',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': _blank_pdf('listing-only.pdf'),
                'il_legal_declaration': 'true',
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, 201, getattr(res, 'data', res.content))
        ticket = Ticket.objects.get(pk=res.data['id'])
        self.assertEqual(ticket.original_price, Decimal('10'))
        self.assertEqual(ticket.asking_price, Decimal('10'))

    def test_il_save_does_not_mutate_equal_face_and_ask(self):
        ticket = Ticket(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('10'),
            asking_price=Decimal('10'),
            status='pending_approval',
            pdf_file='tickets/pdfs/eq.pdf',
        )
        ticket.save()
        ticket.refresh_from_db()
        self.assertEqual(ticket.original_price, Decimal('10'))
        self.assertEqual(ticket.asking_price, Decimal('10'))

    def test_update_price_raises_asking_with_original(self):
        """Regression: updating original alone used to leave a stale lower asking_price."""
        ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('2'),
            asking_price=Decimal('2'),
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/upd.pdf',
            available_quantity=1,
        )
        res = self.client.patch(
            f'/api/users/tickets/{ticket.id}/update-price/',
            {'original_price': 10},
            format='json',
        )
        self.assertEqual(res.status_code, 200, getattr(res, 'data', res.content))
        ticket.refresh_from_db()
        self.assertEqual(ticket.original_price, Decimal('10'))
        self.assertEqual(ticket.asking_price, Decimal('10'))

    def test_quantity_two_does_not_replace_price_with_two(self):
        """Guard against qty/price field mix-ups (e.g. typed 10 with quantity 2 → saved 2)."""
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.add_blank_page(width=200, height=200)
        buf = BytesIO()
        writer.write(buf)
        pdf = SimpleUploadedFile('two-page.pdf', buf.getvalue(), content_type='application/pdf')
        res = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '10',
                'listing_price': '10',
                'available_quantity': '2',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'row_number_0': '1',
                'seat_number_0': '1',
                'row_number_1': '1',
                'seat_number_1': '2',
                'il_legal_declaration': 'true',
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, 201, getattr(res, 'data', res.content))
        tickets = list(Ticket.objects.filter(seller=self.seller).order_by('id'))
        self.assertGreaterEqual(len(tickets), 2)
        for t in tickets[-2:]:
            self.assertEqual(t.original_price, Decimal('10'))
            self.assertEqual(t.asking_price, Decimal('10'))
