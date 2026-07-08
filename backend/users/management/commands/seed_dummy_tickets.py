"""
Seed dummy (system) tickets for key anchor pricing events.

This command is intended for staging/dev data only:
- It is idempotent with respect to the dummy seller: deletes all tickets owned by
  `system_seed_user` before re-seeding.
- It fixes Eden Ben Zaken (Menora) to the real schedule dates: 2026-08-17, 2026-08-18, 2026-08-20.
- It cancels past Omer Adam / Eyal Golan events so they stop appearing in discovery flows.
- It seeds dummy tickets (anchor pricing) for Pe'er Tasi, Ben Tzur (Caesarea), and Eden Ben Zaken (Menora),
  ensuring seeded section labels match the exact SVG layer IDs used by the frontend maps.
- It ensures Ben Tzur Caesarea shows exist on 2026-07-26 and 2026-07-27.

Usage:
  python manage.py seed_dummy_tickets
  python manage.py seed_dummy_tickets --random-seed 123
"""

from __future__ import annotations

import uuid
import random
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from users.models import Artist, Event, Ticket, Venue
from users.secure_ticket_storage import random_ticket_storage_name

User = get_user_model()

TZ_IL = ZoneInfo("Asia/Jerusalem")

SEED_ARTIST_EDEN = "עדן בן זקן"
SEED_ARTIST_PEER = "פאר טסי"
SEED_ARTIST_BEN_TZUR = "בן צור"
SEED_ARTIST_OMER = "עומר אדם"
SEED_ARTIST_EYAL = "אייל גולן"

VENUE_MENORA = "היכל מנורה מבטחים"
VENUE_CAESAREA = "אמפי קיסריה"
VENUE_OTHER = "אחר"

MENORA_SECTION_IDS = [
    "VIP",
    *[f"{n} Lower" for n in range(1, 13)],
    *[f"{n} Upper" for n in range(1, 13)],
]

ANCHOR_PRICES_ILS = [370, 380, 390, 410, 420, 430]

CAESAREA_SECTION_IDS = [
    "אורקסטרה",
    *[f"{n} תחתון" for n in range(1, 7)],
    *[f"{n} אמצע" for n in range(1, 7)],
    *[f"{n} עליון" for n in range(1, 7)],
]

# Minimal PDF bytes (enough to satisfy FileField safety checks / frontend download link).
MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
    b"2 0 obj<< /Type /Pages /Kids [] /Count 0 >>endobj\n"
    b"trailer<< /Root 1 0 R >>\n"
    b"%%EOF\n"
)


def _dt(y: int, m: int, d: int, hour: int, minute: int = 0) -> datetime:
    return datetime(y, m, d, hour, minute, 0, tzinfo=TZ_IL)


def _event_title(*, artist_name: str, venue_label: str, when: datetime) -> str:
    # Matches the pattern used by `seed_august_2026_concerts.py` so the UI looks coherent.
    return f"{artist_name} - {venue_label} — {when.strftime('%d.%m.%Y')}"


@dataclass(frozen=True)
class SectionSeed:
    section_id: str
    price_ils: Decimal
    group_size: int


class Command(BaseCommand):
    help = "Seed dummy tickets with anchor pricing for Pe'er Tasi + Eden Ben Zaken."

    def add_arguments(self, parser):
        parser.add_argument(
            "--random-seed",
            type=int,
            default=None,
            help="Make the section selection deterministic (useful for tests).",
        )

    def handle(self, *args, **options):
        random_seed = options.get("random_seed")
        rng = random.Random(random_seed) if random_seed is not None else random

        seed_user = self._resolve_system_seed_user()

        # 1) Idempotency: delete all tickets owned by the dummy seller first.
        with transaction.atomic():
            Ticket.objects.filter(seller=seed_user).delete()

        # 2) Fix Eden Ben Zaken Menora schedule dates (and cancel duplicates).
        with transaction.atomic():
            self._fix_eden_ben_zaken_menora_schedule(rng=rng)
            self._ensure_ben_tzur_caesarea_schedule()

            # 3) Cancel past Omer Adam / Eyal Golan events.
            self._cancel_past_omer_eyal_events()

        # 4) Seed tickets with anchor pricing (round ILS tiers).
        with transaction.atomic():
            self._seed_dummy_tickets_for_relevant_events(seed_user=seed_user, rng=rng)

        self.stdout.write(self.style.SUCCESS("seed_dummy_tickets: done"))

    def _resolve_system_seed_user(self) -> User:
        email = "system_seed_user@example.com"
        username = "system_seed_user"

        seller, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": username,
                "role": "seller",
                "is_active": True,
                "is_email_verified": True,
                "is_verified_seller": True,
                "accepted_escrow_terms": True,
                "escrow_terms_accepted_at": timezone.now(),
                "account_holder_name": "Seed System",
                "bank_name": "12",
                "branch_number": "345",
                "account_number": "987654321",
            },
        )

        if created:
            seller.set_unusable_password()
            seller.save(update_fields=["password"])
        else:
            changed = False
            if seller.username != username:
                seller.username = username
                changed = True
            if seller.role != "seller":
                seller.role = "seller"
                changed = True
            if not seller.is_active:
                seller.is_active = True
                changed = True
            if not seller.accepted_escrow_terms:
                seller.accepted_escrow_terms = True
                changed = True
            if changed:
                seller.save()

        return seller

    def _cancel_past_omer_eyal_events(self) -> None:
        """Cancel all Omer Adam / Eyal Golan events so they never appear in discovery."""
        Event.objects.filter(
            artist__name__in=[SEED_ARTIST_OMER, SEED_ARTIST_EYAL],
            status="פעיל",
        ).update(status="בוטל")

    def _fix_eden_ben_zaken_menora_schedule(self, *, rng: random.Random) -> None:
        eden_artist, _ = Artist.objects.get_or_create(
            name=SEED_ARTIST_EDEN,
            defaults={
                "genre": "Pop",
                "description": "Eden Ben Zaken — Israeli singer",
                "category": "music",
                "is_international": False,
            },
        )

        menora_place, _ = Venue.objects.get_or_create(name=VENUE_MENORA, city="תל אביב")

        target_dates = [
            _dt(2026, 8, 17, 21, 0),
            _dt(2026, 8, 18, 21, 0),
            _dt(2026, 8, 20, 21, 0),
        ]
        target_by_date = {d.date(): d for d in target_dates}

        # Cancel all Eden + Menora active events that are not on the target dates.
        menora_qs = Event.objects.filter(artist=eden_artist, venue=VENUE_MENORA, status="פעיל")
        for ev in menora_qs:
            d = ev.date.astimezone(TZ_IL).date() if hasattr(ev.date, "astimezone") else ev.date.date()
            if d not in target_by_date:
                ev.status = "בוטל"
                ev.save(update_fields=["status"])

        # For each target date, ensure exactly 1 active event.
        for d, when in target_by_date.items():
            active_on_day = list(
                Event.objects.filter(artist=eden_artist, venue=VENUE_MENORA, status="פעיל", date__date=d)
                .order_by("id")
            )
            if len(active_on_day) > 1:
                for extra in active_on_day[1:]:
                    extra.status = "בוטל"
                    extra.save(update_fields=["status"])

            if not active_on_day:
                Event.objects.create(
                    artist=eden_artist,
                    name=_event_title(artist_name=SEED_ARTIST_EDEN, venue_label=VENUE_MENORA, when=when),
                    date=when,
                    venue=VENUE_MENORA,
                    venue_place=menora_place,
                    city="תל אביב",
                    category="concert",
                    status="פעיל",
                    country="IL",
                    high_demand=True,
                )
            else:
                ev = active_on_day[0]
                ev.artist = eden_artist
                ev.name = _event_title(artist_name=SEED_ARTIST_EDEN, venue_label=VENUE_MENORA, when=when)
                ev.date = when
                ev.venue = VENUE_MENORA
                ev.venue_place = menora_place
                ev.city = "תל אביב"
                ev.category = "concert"
                ev.status = "פעיל"
                ev.country = "IL"
                ev.high_demand = True
                ev.save()

    def _ensure_ben_tzur_caesarea_schedule(self) -> None:
        artist, _ = Artist.objects.get_or_create(
            name=SEED_ARTIST_BEN_TZUR,
            defaults={
                "genre": "Pop",
                "description": "Ben Tzur — Israeli singer",
                "category": "music",
                "is_international": False,
            },
        )
        if artist.category != "music":
            artist.category = "music"
            artist.save(update_fields=["category"])

        caesarea_place, _ = Venue.objects.get_or_create(name=VENUE_CAESAREA, city="קיסריה")

        for when in (_dt(2026, 7, 26, 21, 0), _dt(2026, 7, 27, 21, 0)):
            Event.objects.update_or_create(
                artist=artist,
                date=when,
                defaults={
                    "name": _event_title(
                        artist_name=SEED_ARTIST_BEN_TZUR,
                        venue_label=VENUE_CAESAREA,
                        when=when,
                    ),
                    "venue": VENUE_OTHER,
                    "venue_place": caesarea_place,
                    "city": "קיסריה",
                    "category": "concert",
                    "status": "פעיל",
                    "country": "IL",
                    "high_demand": True,
                },
            )

    def _is_caesarea_event(self, ev: Event) -> bool:
        venue_haystack = " ".join(
            [
                str(getattr(ev, "venue", "") or ""),
                str(getattr(getattr(ev, "venue_place", None), "name", "") or ""),
                str(getattr(ev, "city", "") or ""),
                str(getattr(ev, "name", "") or ""),
            ]
        )
        return (
            "קיסריה" in venue_haystack
            or VENUE_CAESAREA in venue_haystack
            or "caesarea" in venue_haystack.lower()
        )

    def _anchor_price_ils(self, *, rng: random.Random) -> Decimal:
        return Decimal(str(rng.choice(ANCHOR_PRICES_ILS)))

    def _seed_ticket_groups_for_event(
        self,
        *,
        event: Event,
        seed_user: User,
        section_pool: list[str],
        rng: random.Random,
        base_row: int = 1,
    ) -> None:
        # Pick 1–3 distinct map sections for this event.
        k = rng.randint(1, 3)
        chosen_sections = rng.sample(section_pool, k=k)

        # Weighted towards pairs (2 tickets) but sometimes 3/4.
        group_sizes_weighted = [2, 2, 2, 3, 4]

        for idx, section_id in enumerate(chosen_sections, start=1):
            price = self._anchor_price_ils(rng=rng)
            group_size = rng.choice(group_sizes_weighted)
            listing_group_id = str(uuid.uuid4())

            for seat_idx in range(group_size):
                # Ensure stable-ish rows for easier debugging.
                row = str(base_row + ((idx - 1) * 3 + seat_idx) % 20)

                ticket = Ticket(
                    seller=seed_user,
                    event=event,
                    event_name=event.name,
                    event_date=event.date,
                    venue=event.venue_display_name() if hasattr(event, "venue_display_name") else event.venue,
                    custom_section_text=section_id,
                    section_legacy=section_id,
                    row=row,
                    seat_numbers=str(seat_idx + 1),
                    original_price=price,
                    asking_price=price,
                    available_quantity=1,
                    delivery_method="instant",
                    ticket_type="כרטיס אלקטרוני / PDF",
                    verification_status="מאומת",
                    status="active",
                    is_together=True,
                    split_type="כל כמות",
                    listing_group_id=listing_group_id,
                )

                # Ticket.pdf_file is required in DB; use minimal PDF bytes.
                ticket.pdf_file.save(
                    random_ticket_storage_name(".pdf"),
                    ContentFile(MINIMAL_PDF_BYTES),
                    save=False,
                )
                ticket.save()

    def _seed_dummy_tickets_for_relevant_events(self, *, seed_user: User, rng: random.Random) -> None:
        # Seed Eden (Menora).
        eden_events = list(
            Event.objects.filter(artist__name=SEED_ARTIST_EDEN, venue=VENUE_MENORA, status="פעיל").order_by("date")
        )
        for ev in eden_events:
            self._seed_ticket_groups_for_event(
                event=ev,
                seed_user=seed_user,
                section_pool=MENORA_SECTION_IDS,
                rng=rng,
                base_row=1,
            )

        # Seed Caesarea anchor tickets for Pe'er Tasi and Ben Tzur.
        for artist_name, base_row in ((SEED_ARTIST_PEER, 5), (SEED_ARTIST_BEN_TZUR, 8)):
            caesarea_events = list(
                Event.objects.filter(artist__name=artist_name, status="פעיל")
                .select_related("venue_place")
                .order_by("date")
            )
            for ev in caesarea_events:
                if not self._is_caesarea_event(ev):
                    continue
                self._seed_ticket_groups_for_event(
                    event=ev,
                    seed_user=seed_user,
                    section_pool=CAESAREA_SECTION_IDS,
                    rng=rng,
                    base_row=base_row,
                )

