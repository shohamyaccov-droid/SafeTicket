"""Tests for reset_test_data_core and the Django Admin reset action."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from users.models import Artist, Event, Order, Ticket
from users.reset_test_data_core import run_reset_test_data

User = get_user_model()


class ResetTestDataCoreTests(TestCase):
    def test_run_reset_test_data_deletes_orders_and_resets_sold_tickets(self):
        seller = User.objects.create_user(
            username='rst-seller',
            email='rst-seller@example.com',
            password='pass',
            role='seller',
        )
        buyer = User.objects.create_user(
            username='rst-buyer',
            email='rst-buyer@example.com',
            password='pass',
        )
        artist = Artist.objects.create(name='RST Artist')
        event = Event.objects.create(
            artist=artist,
            name='RST Show',
            date=timezone.now(),
            venue='Arena',
            city='TLV',
            country='IL',
        )
        ticket = Ticket.objects.create(
            seller=seller,
            event=event,
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            pdf_file='tickets/pdfs/test.pdf',
            status='sold',
            verification_status='מאומת',
            available_quantity=0,
        )
        Order.objects.create(
            user=buyer,
            ticket=ticket,
            ticket_ids=[ticket.id],
            status='paid',
            total_amount=Decimal('115.00'),
            currency='ILS',
            quantity=1,
        )
        self.assertEqual(Order.objects.count(), 1)

        result = run_reset_test_data()

        self.assertEqual(Order.objects.count(), 0)
        self.assertGreaterEqual(result['orders_deleted'], 1)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'active')
        self.assertEqual(ticket.available_quantity, 1)


class AdminResetTestDataViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_reset_confirm_redirects_non_superuser(self):
        u = User.objects.create_user(
            username='staffonly',
            email='staff@example.com',
            password='pass',
            is_staff=True,
            is_superuser=False,
        )
        self.client.force_login(u)
        r = self.client.get('/admin/users/analyticsevent/reset-test-data/', follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].rstrip('/').endswith('/admin'))

    def test_reset_confirm_get_ok_for_superuser(self):
        u = User.objects.create_superuser('su-reset', 'su-reset@example.com', 'pass')
        self.client.force_login(u)
        r = self.client.get('/admin/users/analyticsevent/reset-test-data/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Reset test data')

    def test_reset_post_redirects_to_analytics_dashboard(self):
        u = User.objects.create_superuser('su-post', 'su-post@example.com', 'pass')
        self.client.force_login(u)
        r = self.client.post('/admin/users/analyticsevent/reset-test-data/', {})
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/users/analyticsevent/dashboard/', r['Location'])
