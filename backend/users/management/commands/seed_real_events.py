"""
Wipe all Events/Tickets (and dependent orders/offers) and seed five real-world launch events
with listings aligned to Bloomfield / Menora / Jerusalem map UIs.

Usage:
  python manage.py seed_real_events --wipe     # full DB reset for events/tickets, then seed
  python manage.py seed_real_events             # seed only (fails if duplicates conflict)

Requires a seller user; creates seed_real_events@safeticket.demo if missing.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Artist, Event, Offer, Order, Ticket, TicketAlert, Venue, VenueSection

User = get_user_model()

TZ_IL = ZoneInfo("Asia/Jerusalem")

SELLER_EMAIL = "seed_real_events@safeticket.demo"
SELLER_USERNAME = "real_events_seed_seller"

VENUE_BLOOMFIELD = "אצטדיון בלומפילד"
VENUE_MENORA = "היכל מנורה מבטחים"
VENUE_JERUSALEM_ARENA = "פיס ארנה ירושלים"

VENUE_SECTIONS = {
    (VENUE_MENORA, "תל אביב"): [
        *[f"{n} תחתון" for n in range(1, 13)],
        *[f"{n} עליון" for n in range(1, 13)],
    ],
    (VENUE_BLOOMFIELD, "תל אביב"): [
        *[str(n) for n in range(201, 210)],
        *[str(n) for n in range(214, 217)],
        *[str(n) for n in range(221, 230)],
        *[str(n) for n in range(234, 237)],
        *[str(n) for n in range(301, 339)],
        *[str(n) for n in range(404, 407)],
        *[str(n) for n in range(419, 432)],
    ],
    (VENUE_JERUSALEM_ARENA, "ירושלים"): [
        *[str(n) for n in range(101, 123)],
        *[str(n) for n in range(301, 331)],
    ],
}


def _pdf(name: str = "ticket.pdf") -> ContentFile:
    body = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    return ContentFile(body, name=name)


def _dt(y: int, m: int, d: int, h: int, minute: int = 0) -> datetime:
    return datetime(y, m, d, h, minute, 0, tzinfo=TZ_IL)


def _price_in_range(lo: int, hi: int, i: int) -> Decimal:
    span = max(1, hi - lo)
    v = lo + (i * 17) % (span + 1)
    return Decimal(v)


class Command(BaseCommand):
    help = "Wipe events/tickets (optional) and seed five realistic launch events with listings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete all Order, Offer, Ticket, TicketAlert, Event rows before seeding.",
        )

    def handle(self, *args, **options):
        do_wipe = options["wipe"]
        if do_wipe:
            self._wipe_catalog()
        with transaction.atomic():
            seller = self._get_seller()
            self.stdout.write(self.style.NOTICE(f"Seller: {seller.email} (pk={seller.pk})"))

            e1 = self._event_football_taifa(
                seller,
                title="מכבי תל אביב נגד מכבי חיפה",
                when=_dt(2026, 5, 12, 20, 0),
            )
            e2 = self._event_football_beitar(
                seller,
                title="מכבי תל אביב נגד בית״ר ירושלים",
                when=_dt(2026, 5, 16, 20, 0),
            )
            e3 = self._event_eyal_golan(seller)
            e4 = self._event_eden_menora(seller)
            e5 = self._event_ben_zur_arena(seller)

        ids = [e1.id, e2.id, e3.id, e4.id, e5.id]
        ev_count = Event.objects.filter(id__in=ids).count()
        tix_count = Ticket.objects.filter(event_id__in=ids).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Events={ev_count}, tickets={tix_count} (seeded rows)."
            )
        )

    def _wipe_catalog(self) -> None:
        self.stdout.write(self.style.WARNING("Wiping Order, Offer, Ticket, TicketAlert, Event…"))
        with transaction.atomic():
            Order.objects.all().delete()
            Offer.objects.all().delete()
            Ticket.objects.all().delete()
            TicketAlert.objects.all().delete()
            Event.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("Wipe complete."))

    def _get_seller(self) -> User:
        u, created = User.objects.get_or_create(
            email=SELLER_EMAIL,
            defaults={
                "username": SELLER_USERNAME,
                "role": "seller",
                "is_verified_seller": True,
            },
        )
        if created:
            u.set_password("RealEventsSeed123!")
        u.role = "seller"
        u.is_verified_seller = True
        u.save()
        return u

    def _get_venue(self, name: str, city: str) -> Venue:
        venue, _ = Venue.objects.get_or_create(name=name, city=city)
        for section_name in VENUE_SECTIONS.get((name, city), []):
            VenueSection.objects.get_or_create(venue=venue, name=section_name)
        return venue

    def _mk_ticket(
        self,
        seller: User,
        event: Event,
        *,
        custom_section: str,
        row: str,
        price: Decimal,
        idx: int,
    ) -> None:
        lg = str(uuid.uuid4())
        t = Ticket(
            seller=seller,
            event=event,
            event_name=event.name,
            event_date=event.date,
            venue=event.venue_display_name(),
            custom_section_text=custom_section,
            row=row,
            original_price=price,
            asking_price=price,
            available_quantity=1,
            verification_status="מאומת",
            status="active",
            listing_group_id=lg,
            ticket_type="כרטיס אלקטרוני / PDF",
            split_type="כל כמות",
            pdf_file=_pdf(name=f"seed_{event.id}_{idx}.pdf"),
        )
        t.save()

    def _event_football_taifa(self, seller: User, title: str, when) -> Event:
        ev = Event.objects.create(
            name=title,
            date=when,
            venue=VENUE_BLOOMFIELD,
            venue_place=self._get_venue(VENUE_BLOOMFIELD, "תל אביב"),
            city="תל אביב",
            category="sport",
            status="פעיל",
            country="IL",
            home_team="מכבי תל אביב",
            away_team="מכבי חיפה",
        )
        # ~15 tickets across sections 319, 328, 221, 229, 419 (reference layout)
        base_sections = [319, 328, 221, 229, 419]
        for i in range(15):
            sec = base_sections[i % len(base_sections)]
            p = _price_in_range(150, 350, i)
            self._mk_ticket(
                seller,
                ev,
                custom_section=str(sec),
                row=str(1 + (i % 12)),
                price=p,
                idx=i,
            )
        return ev

    def _event_football_beitar(self, seller: User, title: str, when) -> Event:
        ev = Event.objects.create(
            name=title,
            date=when,
            venue=VENUE_BLOOMFIELD,
            venue_place=self._get_venue(VENUE_BLOOMFIELD, "תל אביב"),
            city="תל אביב",
            category="sport",
            status="פעיל",
            country="IL",
            home_team="מכבי תל אביב",
            away_team='בית"ר ירושלים',
        )
        base_sections = [301, 309, 214, 216]
        # ~15 listings: cycle sections with distinct rows
        for i in range(15):
            sec = base_sections[i % len(base_sections)]
            p = _price_in_range(150, 300, i)
            self._mk_ticket(
                seller,
                ev,
                custom_section=str(sec),
                row=str(1 + (i % 15)),
                price=p,
                idx=i,
            )
        return ev

    def _event_eyal_golan(self, seller: User) -> Event:
        artist, _ = Artist.objects.get_or_create(
            name="אייל גולן",
            defaults={"genre": "Mizrahi", "description": "Seed artist"},
        )
        when = _dt(2026, 6, 18, 20, 0)
        ev = Event.objects.create(
            artist=artist,
            name="אייל גולן - בלומפילד",
            date=when,
            venue=VENUE_BLOOMFIELD,
            venue_place=self._get_venue(VENUE_BLOOMFIELD, "תל אביב"),
            city="תל אביב",
            category="concert",
            status="פעיל",
            country="IL",
        )
        # 25 listings across tiers (200s–500s + key 300s/400s)
        sections = [
            214,
            216,
            221,
            229,
            301,
            304,
            307,
            309,
            312,
            315,
            319,
            322,
            325,
            328,
            404,
            408,
            419,
            423,
            427,
            431,
            502,
            506,
            510,
            514,
            518,
        ]
        for i, sec in enumerate(sections):
            p = _price_in_range(250, 550, i)
            self._mk_ticket(
                seller,
                ev,
                custom_section=str(sec),
                row=str(1 + (i % 20)),
                price=p,
                idx=i,
            )
        return ev

    def _event_eden_menora(self, seller: User) -> Event:
        artist, _ = Artist.objects.get_or_create(
            name="עדן חסון",
            defaults={"genre": "Pop", "description": "Seed artist"},
        )
        when = _dt(2026, 6, 25, 20, 45)
        ev = Event.objects.create(
            artist=artist,
            name="עדן חסון - היכל מנורה",
            date=when,
            venue=VENUE_MENORA,
            venue_place=self._get_venue(VENUE_MENORA, "תל אביב"),
            city="תל אביב",
            category="concert",
            status="פעיל",
            country="IL",
        )
        base = ["1 תחתון", "5 תחתון", "1 עליון", "12 עליון"]
        for i in range(15):
            sec = base[i % len(base)]
            p = _price_in_range(200, 450, i)
            self._mk_ticket(
                seller,
                ev,
                custom_section=str(sec),
                row=str(1 + (i % 18)),
                price=p,
                idx=i,
            )
        return ev

    def _event_ben_zur_arena(self, seller: User) -> Event:
        artist, _ = Artist.objects.get_or_create(
            name="בן צור",
            defaults={"genre": "Pop", "description": "Seed artist"},
        )
        when = _dt(2026, 5, 28, 21, 0)
        ev = Event.objects.create(
            artist=artist,
            name="בן צור - הופעת ענק",
            date=when,
            venue=VENUE_JERUSALEM_ARENA,
            venue_place=self._get_venue(VENUE_JERUSALEM_ARENA, "ירושלים"),
            city="ירושלים",
            category="concert",
            status="פעיל",
            country="IL",
        )
        prices_cycle = [Decimal("199"), Decimal("299"), Decimal("399")]
        sections = [110, 111, 315, 316]
        for i in range(15):
            sec = sections[i % len(sections)]
            p = prices_cycle[i % 3]
            self._mk_ticket(
                seller,
                ev,
                custom_section=str(sec),
                row=str(1 + (i % 14)),
                price=p,
                idx=i,
            )
        return ev
