"""15% platform fee model: 10% buyer + 5% seller; admin dashboard aggregates both."""
from __future__ import annotations

from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, Ticket
from users.pricing import compute_order_price_breakdown

User = get_user_model()


def _pdf():
    return b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'


class FifteenPercentFeeTests(TestCase):
    def test_compute_order_price_breakdown_list_price(self):
        seller = User.objects.create_user(username='s1', email='s1@t.com', password='x', role='seller')
        artist = Artist.objects.create(name='Art')
        ev = Event.objects.create(
            artist=artist,
            name='Ev',
            date=timezone.now() + timedelta(days=20),
            venue='V',
            city='Tel Aviv',
            country='IL',
        )
        t = Ticket(
            seller=seller,
            event=ev,
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            available_quantity=1,
            status='active',
            verification_status='מאומת',
        )
        t.pdf_file.save('f.pdf', ContentFile(_pdf()), save=True)

        bd = compute_order_price_breakdown(Decimal('110'), None, t, 1)
        self.assertEqual(bd['final_negotiated_price'], Decimal('100'))
        self.assertEqual(bd['buyer_service_fee'], Decimal('10'))
        self.assertEqual(bd['seller_service_fee'], Decimal('5'))
        self.assertEqual(bd['net_seller_revenue'], Decimal('95'))
        self.assertEqual(bd['total_paid_by_buyer'], Decimal('110'))

    def test_admin_dashboard_stats_includes_seller_fee_in_platform_fees_and_ils(self):
        staff = User.objects.create_user(
            username='admin',
            email='admin@t.com',
            password='x',
            is_staff=True,
            is_superuser=True,
        )
        seller = User.objects.create_user(username='s2', email='s2@t.com', password='x', role='seller')
        artist = Artist.objects.create(name='A2')
        ev = Event.objects.create(
            artist=artist,
            name='E2',
            date=timezone.now() + timedelta(days=20),
            venue='V',
            city='London',
            country='GB',
        )
        t = Ticket(
            seller=seller,
            event=ev,
            event_name='E2',
            original_price=Decimal('480'),
            asking_price=Decimal('480'),
            available_quantity=0,
            status='sold',
            verification_status='מאומת',
        )
        t.pdf_file.save('g.pdf', ContentFile(_pdf()), save=True)

        Order.objects.create(
            user=User.objects.create_user(username='b2', email='b2@t.com', password='x', role='buyer'),
            ticket=t,
            total_amount=Decimal('528.00'),
            total_paid_by_buyer=Decimal('528.00'),
            status='paid',
            currency='GBP',
            quantity=1,
            event_name='E2',
            buyer_service_fee=Decimal('48.00'),
            seller_service_fee=Decimal('24.00'),
            final_negotiated_price=Decimal('480.00'),
            net_seller_revenue=Decimal('456.00'),
        )

        c = APIClient()
        c.force_authenticate(user=staff)
        r = c.get('/api/users/admin/dashboard/stats/')
        self.assertEqual(r.status_code, 200, r.content)
        payload = r.json()
        gbp = payload['all_time']['by_currency'].get('GBP', {})
        self.assertEqual(Decimal(str(gbp.get('platform_fees'))), Decimal('72'))
        ils_fees = Decimal(str(payload['all_time']['totals_ils']['platform_fees_ils']))
        self.assertGreater(ils_fees, Decimal('300'))
