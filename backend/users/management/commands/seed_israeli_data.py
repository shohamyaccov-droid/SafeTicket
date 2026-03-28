"""
Populate the database with realistic Israeli-market demo data (artists, venues, events, sellers, tickets).

Usage:
  python manage.py seed_israeli_data
  python manage.py seed_israeli_data --reset

WARNING: --reset deletes existing Artists/Events/Tickets created by this command (matched by seeded seller email prefix).
For a clean wipe of ALL tickets/events/artists, use only on dev DB.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from django.contrib.auth import get_user_model

from users.models import Artist, Event, Ticket

User = get_user_model()

SELLER_EMAIL = 'seed_israeli_seller@safeticket.demo'
BUYER_EMAIL = 'seed_israeli_buyer@safeticket.demo'
ADMIN_USER = 'seed_israeli_admin'
ADMIN_EMAIL = 'seed_israeli_admin@safeticket.demo'


def _pdf(name: str = 'demo.pdf') -> ContentFile:
    body = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
    return ContentFile(body, name=name)


class Command(BaseCommand):
    help = 'Seed Israeli demo artists, events, and listings (Omer Adam, Noa Kirel, Park HaYarkon, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Remove demo seller listings (by seller email) before seeding',
        )

    def handle(self, *args, **options):
        reset = options['reset']
        if reset:
            u = User.objects.filter(email=SELLER_EMAIL).first()
            if u:
                Ticket.objects.filter(seller=u).delete()
                self.stdout.write(self.style.WARNING('Removed tickets for demo seller.'))

        seller, _ = User.objects.get_or_create(
            email=SELLER_EMAIL,
            defaults={
                'username': 'israeli_demo_seller',
                'role': 'seller',
            },
        )
        seller.set_password('DemoSeller123!')
        seller.role = 'seller'
        seller.save()

        buyer, _ = User.objects.get_or_create(
            email=BUYER_EMAIL,
            defaults={'username': 'israeli_demo_buyer', 'role': 'buyer'},
        )
        buyer.set_password('DemoBuyer123!')
        buyer.save()

        admin, created = User.objects.get_or_create(
            email=ADMIN_EMAIL,
            defaults={
                'username': ADMIN_USER,
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            admin.set_password('DemoAdmin123!')
            admin.is_staff = True
            admin.is_superuser = True
            admin.save()
            self.stdout.write(self.style.SUCCESS('Created demo superuser (approve tickets in admin).'))

        # Artists typical Israeli pop scene
        omer, _ = Artist.objects.get_or_create(
            name='עומר אדם',
            defaults={'description': 'זמר והופעות חיות — דאטא לסימולציה בלבד', 'genre': 'Pop'},
        )
        noa, _ = Artist.objects.get_or_create(
            name='נועה קירל',
            defaults={'description': 'זמרת — דאטא לסימולציה בלבד', 'genre': 'Pop'},
        )

        future_a = timezone.now() + timedelta(days=45, hours=20)
        future_b = timezone.now() + timedelta(days=52, hours=19)

        ev_yarkon, _ = Event.objects.update_or_create(
            artist=omer,
            name='עומר אדם — הופעה בפארק הירקון',
            defaults={
                'date': future_a,
                'venue': 'אחר',
                'city': 'תל אביב',
                'category': 'concert',
                'status': 'פעיל',
            },
        )

        ev_bloomfield, _ = Event.objects.update_or_create(
            artist=noa,
            name='נועה קירל — בלומפילד חיפה',
            defaults={
                'date': future_b,
                'venue': 'בלומפילד',
                'city': 'חיפה',
                'category': 'concert',
                'status': 'פעיל',
            },
        )

        for price, seat_row, ev in (
            (Decimal('280'), '14', ev_yarkon),
            (Decimal('300'), '8', ev_bloomfield),
        ):
            if Ticket.objects.filter(event=ev, seller=seller, seat_row=seat_row).exists():
                continue
            t = Ticket(
                seller=seller,
                event=ev,
                event_name=ev.name,
                event_date=ev.date,
                venue=ev.get_venue_display() if hasattr(ev, 'get_venue_display') else ev.venue,
                original_price=price,
                available_quantity=1,
                verification_status='מאומת',
                status='active',
                listing_group_id=str(uuid.uuid4()),
                ticket_type='כרטיס אלקטרוני / PDF',
                split_type='כל כמות',
                seat_row=seat_row,
                pdf_file=_pdf(name=f'seed_{ev.id}_{seat_row}.pdf'),
            )
            t.save()
            self.stdout.write(self.style.SUCCESS(f'Ticket id={t.id} event_id={ev.id} price={price}'))

        self.stdout.write(
            self.style.SUCCESS(
                '\nDone.\n'
                f'  Seller: {SELLER_EMAIL} / DemoSeller123!\n'
                f'  Buyer:  {BUYER_EMAIL} / DemoBuyer123!\n'
                f'  Admin:  {ADMIN_EMAIL} / DemoAdmin123! (new installs only)\n'
            )
        )
