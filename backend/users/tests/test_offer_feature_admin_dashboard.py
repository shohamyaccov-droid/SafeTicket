from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Event, Offer, Order, Ticket


User = get_user_model()


class OfferFeatureTestBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='offer-seller',
            email='offer-seller@example.com',
            password='test-pass-123',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='offer-buyer',
            email='offer-buyer@example.com',
            password='test-pass-123',
            role='buyer',
        )
        self.outsider = User.objects.create_user(
            username='offer-outsider',
            email='offer-outsider@example.com',
            password='test-pass-123',
            role='buyer',
        )
        self.admin = User.objects.create_user(
            username='offer-admin',
            email='offer-admin@example.com',
            password='test-pass-123',
            is_staff=True,
        )
        self.event = Event.objects.create(
            name='Offer Dashboard Event',
            date=timezone.now() + timedelta(days=30),
            venue='Offer Arena',
            city='Tel Aviv',
            country='IL',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            original_price=Decimal('120.00'),
            asking_price=Decimal('100.00'),
            status='active',
            verification_status='מאומת',
            available_quantity=2,
        )

    def create_offer(self, **overrides):
        values = {
            'buyer': self.buyer,
            'ticket': self.ticket,
            'amount': Decimal('170.00'),
            'quantity': 2,
            'status': 'pending',
            'expires_at': timezone.now() + timedelta(hours=48),
        }
        values.update(overrides)
        return Offer.objects.create(**values)


class OfferApiSecurityAndValidationTests(OfferFeatureTestBase):
    def test_valid_offer_is_private_to_participants_and_ignores_chain_injection(self):
        unrelated = self.create_offer(buyer=self.outsider, amount=Decimal('180.00'))
        self.client.force_authenticate(self.buyer)
        response = self.client.post(
            '/api/users/offers/',
            {
                'ticket': self.ticket.pk,
                'amount': '170.00',
                'quantity': 2,
                'parent_offer': unrelated.pk,
                'counter_offer': unrelated.pk,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        created = Offer.objects.get(pk=response.data['id'])
        self.assertIsNone(created.parent_offer_id)
        self.assertIsNone(created.counter_offer_id)
        self.assertNotIn('seller_email', response.data)

        self.client.force_authenticate(self.outsider)
        hidden = self.client.get(f'/api/users/offers/{created.pk}/')
        self.assertEqual(hidden.status_code, 404)

    def test_offer_quantity_must_fit_locked_inventory(self):
        self.client.force_authenticate(self.buyer)
        for quantity in (0, -1, 3):
            with self.subTest(quantity=quantity):
                response = self.client.post(
                    '/api/users/offers/',
                    {
                        'ticket': self.ticket.pk,
                        'amount': '50.00',
                        'quantity': quantity,
                    },
                    format='json',
                )
                self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Offer.objects.filter(buyer=self.buyer).exists())

    def test_seller_cannot_offer_on_own_ticket(self):
        self.client.force_authenticate(self.seller)
        response = self.client.post(
            '/api/users/offers/',
            {'ticket': self.ticket.pk, 'amount': '50.00', 'quantity': 1},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_only_recipient_can_accept_or_reject(self):
        offer = self.create_offer()
        self.client.force_authenticate(self.buyer)
        self.assertEqual(
            self.client.post(f'/api/users/offers/{offer.pk}/accept/', {}, format='json').status_code,
            403,
        )
        self.assertEqual(
            self.client.post(f'/api/users/offers/{offer.pk}/reject/', {}, format='json').status_code,
            403,
        )

        self.client.force_authenticate(self.seller)
        accepted = self.client.post(
            f'/api/users/offers/{offer.pk}/accept/',
            {},
            format='json',
        )
        self.assertEqual(accepted.status_code, 200, accepted.data)
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'accepted')
        self.assertIsNotNone(offer.checkout_expires_at)

    def test_expired_offer_cannot_be_rejected(self):
        offer = self.create_offer(expires_at=timezone.now() - timedelta(seconds=1))
        self.client.force_authenticate(self.seller)
        response = self.client.post(
            f'/api/users/offers/{offer.pk}/reject/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'expired')

    def test_counter_rejects_non_finite_amount_and_enforces_round_owner(self):
        offer = self.create_offer()
        self.client.force_authenticate(self.buyer)
        wrong_party = self.client.post(
            f'/api/users/offers/{offer.pk}/counter/',
            {'amount': '160.00'},
            format='json',
        )
        self.assertEqual(wrong_party.status_code, 403)

        self.client.force_authenticate(self.seller)
        invalid = self.client.post(
            f'/api/users/offers/{offer.pk}/counter/',
            {'amount': 'NaN'},
            format='json',
        )
        self.assertEqual(invalid.status_code, 400)
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'pending')

    def test_database_constraints_reject_impossible_offer_values(self):
        for field_values in (
            {'amount': Decimal('0.00')},
            {'quantity': 0},
            {'offer_round_count': 3},
        ):
            with self.subTest(field_values=field_values):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        self.create_offer(**field_values)


class AdminOfferDashboardApiTests(OfferFeatureTestBase):
    def test_admin_endpoint_requires_staff(self):
        anonymous = self.client.get('/api/users/admin/offers/')
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_authenticate(self.buyer)
        forbidden = self.client.get('/api/users/admin/offers/')
        self.assertEqual(forbidden.status_code, 403)

    def test_admin_metrics_filters_and_purchase_conversion(self):
        accepted = self.create_offer(
            status='accepted',
            accepted_at=timezone.now(),
            checkout_expires_at=timezone.now() + timedelta(hours=24),
        )
        self.create_offer(
            buyer=self.outsider,
            amount=Decimal('160.00'),
            status='rejected',
        )
        Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            related_offer=accepted,
            status='completed',
            total_amount=Decimal('190.40'),
            total_paid_by_buyer=Decimal('190.40'),
            final_negotiated_price=accepted.amount,
            net_seller_revenue=accepted.amount,
            buyer_service_fee=Decimal('20.40'),
            quantity=accepted.quantity,
            event_name=self.event.name,
        )

        self.client.force_authenticate(self.admin)
        response = self.client.get(
            '/api/users/admin/offers/',
            {'status': 'accepted', 'days': 'all', 'q': self.buyer.username},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        row = response.data['results'][0]
        self.assertEqual(row['buyer']['email'], self.buyer.email)
        self.assertEqual(row['seller']['email'], self.seller.email)
        self.assertTrue(row['purchase_completed'])
        self.assertIsNotNone(row['order_id'])

        metrics = response.data['metrics']
        self.assertEqual(metrics['total_offers'], 2)
        self.assertEqual(metrics['status_counts']['accepted'], 1)
        self.assertEqual(metrics['status_counts']['rejected'], 1)
        self.assertEqual(metrics['completed_purchases'], 1)
        self.assertEqual(metrics['purchase_conversion_percent'], '100.00')
        self.assertEqual(len(metrics['daily_activity']), 14)

    def test_admin_endpoint_validates_filter_and_caps_page_size(self):
        self.create_offer()
        self.client.force_authenticate(self.admin)
        invalid = self.client.get('/api/users/admin/offers/', {'status': 'deleted'})
        self.assertEqual(invalid.status_code, 400)

        response = self.client.get(
            '/api/users/admin/offers/',
            {'page_size': 10000, 'days': '30'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['page_size'], 100)
