"""mark_tickets_taken must lock seed/dummy inventory (incl. Eden / event id / seed seller)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from users.models import Artist, Event, Ticket
from users.ticket_status import TICKET_STATUS_TAKEN

User = get_user_model()


class MarkTicketsTakenCommandTests(TestCase):
    def setUp(self):
        self.seed_seller = User.objects.create_user(
            username='system_seed_user',
            email='system_seed_user@example.com',
            password='x',
            role='seller',
        )
        self.real_seller = User.objects.create_user(
            username='real_seller',
            email='real_seller@example.com',
            password='x',
            role='seller',
        )
        self.eden = Artist.objects.create(name='עדן בן זקן')
        self.other_artist = Artist.objects.create(name='אמן אחר')
        self.event_83 = Event.objects.create(
            id=83,
            artist=self.eden,
            name='עדן בן זקן - מנורה',
            date=timezone.now() + timedelta(days=40),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            country='IL',
            category='concert',
            status='פעיל',
        )
        self.other_event = Event.objects.create(
            artist=self.other_artist,
            name='Other Show',
            date=timezone.now() + timedelta(days=50),
            venue='ישראל',
            city='תל אביב',
            country='IL',
            category='concert',
            status='פעיל',
        )

        self.seed_on_83 = Ticket.objects.create(
            seller=self.seed_seller,
            event=self.event_83,
            original_price=Decimal('250'),
            asking_price=Decimal('250'),
            available_quantity=2,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/seed83.pdf',
            custom_section_text='VIP',
        )
        self.test_section = Ticket.objects.create(
            seller=self.real_seller,
            event=self.other_event,
            original_price=Decimal('149'),
            asking_price=Decimal('149'),
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/test-zone.pdf',
            custom_section_text='אזור בדיקה A',
        )
        self.real_listing = Ticket.objects.create(
            seller=self.real_seller,
            event=self.other_event,
            original_price=Decimal('300'),
            asking_price=Decimal('300'),
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/real.pdf',
            custom_section_text='1 Lower',
        )

    def test_marks_seed_seller_event_83_and_test_section(self):
        call_command('mark_tickets_taken')
        self.seed_on_83.refresh_from_db()
        self.test_section.refresh_from_db()
        self.real_listing.refresh_from_db()
        self.assertEqual(self.seed_on_83.status, TICKET_STATUS_TAKEN)
        self.assertEqual(self.seed_on_83.available_quantity, 0)
        self.assertEqual(self.test_section.status, TICKET_STATUS_TAKEN)
        # Real seller listing on a non-Eden event must stay buyable
        self.assertEqual(self.real_listing.status, 'active')
        self.assertEqual(self.real_listing.available_quantity, 1)

    def test_dry_run_does_not_update(self):
        call_command('mark_tickets_taken', dry_run=True)
        self.seed_on_83.refresh_from_db()
        self.assertEqual(self.seed_on_83.status, 'active')

    def test_explicit_ticket_ids(self):
        call_command('mark_tickets_taken', ticket_ids=str(self.real_listing.id))
        self.real_listing.refresh_from_db()
        self.seed_on_83.refresh_from_db()
        self.assertEqual(self.real_listing.status, TICKET_STATUS_TAKEN)
        self.assertEqual(self.seed_on_83.status, 'active')
