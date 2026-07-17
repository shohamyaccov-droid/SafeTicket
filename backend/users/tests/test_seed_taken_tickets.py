"""Tests for seed_taken_tickets — empty-event FOMO / map QA seeding."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from users.models import Artist, Event, Ticket
from users.secure_ticket_storage import random_ticket_storage_name
from users.ticket_status import TICKET_STATUS_TAKEN

User = get_user_model()
TZ_IL = ZoneInfo('Asia/Jerusalem')

MINIMAL_PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


def _dt(y, m, d, h=21):
    return datetime(y, m, d, h, 0, 0, tzinfo=TZ_IL)


class SeedTakenTicketsTests(TestCase):
    def setUp(self):
        self.artist, _ = Artist.objects.get_or_create(
            name='Seed Taken Artist',
            defaults={'category': 'music', 'genre': 'Pop'},
        )
        self.empty_menora = Event.objects.create(
            name='Empty Menora Show',
            artist=self.artist,
            date=_dt(2026, 9, 1),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            status='פעיל',
        )
        self.empty_caesarea = Event.objects.create(
            name='Empty Caesarea Show',
            artist=self.artist,
            date=_dt(2026, 9, 2),
            venue='אמפי קיסריה',
            city='קיסריה',
            status='פעיל',
        )
        self.stocked = Event.objects.create(
            name='Already Has Tickets',
            artist=self.artist,
            date=_dt(2026, 9, 3),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            status='פעיל',
        )
        seller = User.objects.create_user(
            username='existing_seller',
            email='existing_seller@example.com',
            password='x',
            role='seller',
        )
        t = Ticket(
            seller=seller,
            event=self.stocked,
            event_name=self.stocked.name,
            event_date=self.stocked.date,
            venue=self.stocked.venue,
            custom_section_text='1 Lower',
            section_legacy='1 Lower',
            original_price=100,
            asking_price=100,
            available_quantity=1,
            status='active',
            delivery_method='instant',
            ticket_type='כרטיס אלקטרוני / PDF',
            verification_status='מאומת',
        )
        t.pdf_file.save(random_ticket_storage_name('.pdf'), ContentFile(MINIMAL_PDF), save=False)
        t.save()

        self.cancelled_empty = Event.objects.create(
            name='Cancelled Empty',
            artist=self.artist,
            date=_dt(2026, 9, 4),
            venue='היכל מנורה מבטחים',
            status='בוטל',
        )

    def test_seeds_only_empty_active_events_as_taken(self):
        call_command('seed_taken_tickets', random_seed=7)

        menora_qs = Ticket.objects.filter(event=self.empty_menora)
        caesarea_qs = Ticket.objects.filter(event=self.empty_caesarea)
        self.assertTrue(4 <= menora_qs.count() <= 6)
        self.assertTrue(4 <= caesarea_qs.count() <= 6)
        self.assertTrue(all(t.status == TICKET_STATUS_TAKEN for t in menora_qs))
        self.assertTrue(all(t.available_quantity == 0 for t in menora_qs))
        self.assertTrue(all(t.status == TICKET_STATUS_TAKEN for t in caesarea_qs))

        # Menora sections must match interactive SVG IDs
        for t in menora_qs:
            section = t.get_section_display()
            self.assertTrue(
                section == 'VIP'
                or section.endswith(' Lower')
                or section.endswith(' Upper'),
                msg=f'unexpected Menora section {section!r}',
            )

        # Stocked event untouched
        self.assertEqual(Ticket.objects.filter(event=self.stocked).count(), 1)
        self.assertEqual(Ticket.objects.filter(event=self.stocked).first().status, 'active')

        # Cancelled empty event ignored
        self.assertEqual(Ticket.objects.filter(event=self.cancelled_empty).count(), 0)

    def test_idempotent_second_run_does_not_add_more(self):
        call_command('seed_taken_tickets', random_seed=3)
        first = Ticket.objects.filter(event=self.empty_menora).count()
        call_command('seed_taken_tickets', random_seed=3)
        second = Ticket.objects.filter(event=self.empty_menora).count()
        self.assertEqual(first, second)

    def test_dry_run_creates_nothing(self):
        call_command('seed_taken_tickets', dry_run=True, random_seed=1)
        self.assertEqual(Ticket.objects.filter(event=self.empty_menora).count(), 0)
        self.assertEqual(Ticket.objects.filter(event=self.empty_caesarea).count(), 0)

    def test_does_not_touch_event_when_explicit_ids_already_stocked(self):
        before = Ticket.objects.filter(event=self.stocked).count()
        call_command(
            'seed_taken_tickets',
            event_ids=str(self.stocked.id),
            random_seed=1,
        )
        self.assertEqual(Ticket.objects.filter(event=self.stocked).count(), before)
