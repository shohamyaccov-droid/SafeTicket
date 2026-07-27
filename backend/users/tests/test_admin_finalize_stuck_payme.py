"""Admin action: force-finalize stuck PayMe orders (pending_payment or cancelled)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone

from users.admin import OrderAdmin
from users.models import Artist, Event, Order, SellerPayout, Ticket
from users.payments import finalize_pending_order_to_paid

User = get_user_model()


def _attach_messages(request):
    setattr(request, 'session', {})
    setattr(request, '_messages', FallbackStorage(request))


class FinalizeStuckPaymeOrdersAdminTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = OrderAdmin(Order, self.site)
        self.factory = RequestFactory()
        self.staff = User.objects.create_superuser(
            username='admin_finalize',
            email='admin_finalize@test.invalid',
            password='x',
        )
        future = timezone.now() + timedelta(days=30)
        self.seller = User.objects.create_user(
            username='finalize_seller',
            email='finalize_seller@test.invalid',
            password='x',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='finalize_buyer',
            email='finalize_buyer@test.invalid',
            password='x',
            role='buyer',
        )
        artist = Artist.objects.create(name='Finalize Artist')
        self.event = Event.objects.create(
            name='Finalize Event',
            artist=artist,
            date=future,
            venue='מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        pdf = SimpleUploadedFile(
            't.pdf',
            b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n',
            content_type='application/pdf',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            available_quantity=1,
            status='reserved',
            reserved_by=self.buyer,
            reserved_at=timezone.now(),
            pdf_file=pdf,
            verification_status='מאומת',
        )
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            status='pending_payment',
            total_amount=Decimal('107.00'),
            total_paid_by_buyer=Decimal('107.00'),
            currency='ILS',
            quantity=1,
            event_name=self.event.name,
            ticket_ids=[self.ticket.id],
            payme_transaction_id='SALE-STUCK-1',
            payme_status='initialized',
        )

    def test_confirmation_page_does_not_finalize(self):
        request = self.factory.post('/admin/users/order/', {'_selected_action': [str(self.order.pk)]})
        request.user = self.staff
        _attach_messages(request)

        response = self.admin.finalize_stuck_payme_orders(request, Order.objects.filter(pk=self.order.pk))
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending_payment')
        self.assertFalse(SellerPayout.objects.filter(order=self.order).exists())

    def test_apply_finalizes_eligible_order(self):
        request = self.factory.post(
            '/admin/users/order/',
            {
                '_selected_action': [str(self.order.pk)],
                'apply': '1',
                'action': 'finalize_stuck_payme_orders',
            },
        )
        request.user = self.staff
        _attach_messages(request)

        response = self.admin.finalize_stuck_payme_orders(request, Order.objects.filter(pk=self.order.pk))
        self.assertIsNone(response)
        self.order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.ticket.status, 'sold')
        self.assertEqual(self.ticket.available_quantity, 0)
        self.assertTrue(SellerPayout.objects.filter(order=self.order).exists())

    def test_apply_finalizes_cancelled_order_and_reclaims_ticket(self):
        """Apple Pay paid in PayMe, then TradeTix abandoned cleanup set cancelled + released inventory."""
        self.ticket.status = 'active'
        self.ticket.available_quantity = 1
        self.ticket.reserved_by = None
        self.ticket.reserved_at = None
        self.ticket.save(
            update_fields=['status', 'available_quantity', 'reserved_by', 'reserved_at', 'updated_at']
        )
        self.order.status = 'cancelled'
        self.order.held_ticket = None
        self.order.held_quantity = 0
        self.order.payme_status = 'initialized'
        self.order.save(
            update_fields=['status', 'held_ticket', 'held_quantity', 'payme_status', 'updated_at']
        )

        request = self.factory.post(
            '/admin/users/order/',
            {
                '_selected_action': [str(self.order.pk)],
                'apply': '1',
                'action': 'finalize_stuck_payme_orders',
            },
        )
        request.user = self.staff
        _attach_messages(request)

        response = self.admin.finalize_stuck_payme_orders(request, Order.objects.filter(pk=self.order.pk))
        self.assertIsNone(response)
        self.order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.order.user_id, self.buyer.id)
        self.assertEqual(self.ticket.status, 'sold')
        self.assertEqual(self.ticket.available_quantity, 0)
        self.assertTrue(SellerPayout.objects.filter(order=self.order).exists())

    def test_force_from_admin_required_for_cancelled_via_payments_helper(self):
        self.order.status = 'cancelled'
        self.order.save(update_fields=['status'])
        self.ticket.status = 'active'
        self.ticket.available_quantity = 1
        self.ticket.save(update_fields=['status', 'available_quantity', 'updated_at'])

        ok, err = finalize_pending_order_to_paid(self.order.pk, source='webhook')
        self.assertFalse(ok)
        self.assertEqual(err, 'order_not_pending')

        ok, err = finalize_pending_order_to_paid(
            self.order.pk,
            source='admin_manual_finalize',
            force_from_admin=True,
        )
        self.assertTrue(ok, err)
        self.order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.ticket.status, 'sold')

    def test_skips_orders_without_payme_sale_id(self):
        self.order.payme_transaction_id = ''
        self.order.save(update_fields=['payme_transaction_id'])
        request = self.factory.post('/admin/users/order/', {'_selected_action': [str(self.order.pk)]})
        request.user = self.staff
        _attach_messages(request)

        response = self.admin.finalize_stuck_payme_orders(request, Order.objects.filter(pk=self.order.pk))
        self.assertIsNone(response)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending_payment')
