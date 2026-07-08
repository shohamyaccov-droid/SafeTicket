from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from users.models import Artist, Event, Ticket, Venue

User = get_user_model()

TZ_IL = ZoneInfo("Asia/Jerusalem")

SYSTEM_SEED_USERNAME = "system_seed_user"

EDEN = "עדן בן זקן"
PEER = "פאר טסי"
BEN_TZUR = "בן צור"
MOR = "מור רביעי"
OMER = "עומר אדם"
EYAL = "אייל גולן"

VENUE_MENORA = "היכל מנורה מבטחים"

VENUE_CAESAREA_PLACE = "אמפי קיסריה"

MENORA_SECTION_IDS = [
    "VIP",
    *[f"{n} Lower" for n in range(1, 13)],
    *[f"{n} Upper" for n in range(1, 13)],
]

CAESAREA_SECTION_IDS = [
    "אורקסטרה",
    *[f"{n} תחתון" for n in range(1, 7)],
    *[f"{n} אמצע" for n in range(1, 7)],
    *[f"{n} עליון" for n in range(1, 7)],
]

PREMIUM_PRICES_ILS = {550, 580, 600, 620, 650}
HIGH_PRICES_ILS = {420, 450, 480}
MID_PRICES_ILS = {330, 350, 380}
BASE_PRICES_ILS = {250, 270, 290}
FALLBACK_PRICES_ILS = {350, 380, 400}
ALL_ALLOWED_PRICES_ILS = (
    PREMIUM_PRICES_ILS | HIGH_PRICES_ILS | MID_PRICES_ILS | BASE_PRICES_ILS | FALLBACK_PRICES_ILS
)


def _dt(y: int, m: int, d: int, hour: int, minute: int = 0) -> datetime:
    return datetime(y, m, d, hour, minute, 0, tzinfo=TZ_IL)


class SeedDummyTicketsTests(TestCase):
    def setUp(self):
        # Use get_or_create to play nicely with any global seed fixtures run at test DB startup.
        self.eden_artist, _ = Artist.objects.get_or_create(name=EDEN, defaults={"category": "music", "genre": "Pop"})
        self.peer_artist, _ = Artist.objects.get_or_create(
            name=PEER, defaults={"category": "music", "genre": "Hip-Hop / Rap"}
        )
        self.omer_artist, _ = Artist.objects.get_or_create(name=OMER, defaults={"category": "music", "genre": "Pop"})
        self.eyal_artist, _ = Artist.objects.get_or_create(
            name=EYAL, defaults={"category": "music", "genre": "Mizrahi"}
        )
        self.mor_artist, _ = Artist.objects.get_or_create(
            name=MOR, defaults={"category": "music", "genre": "Pop"}
        )

        self.menora_venue, _ = Venue.objects.get_or_create(name=VENUE_MENORA, city="תל אביב")
        self.caesarea_place, _ = Venue.objects.get_or_create(name=VENUE_CAESAREA_PLACE, city="קיסריה")

        # Eden (Menora) schedule-fix inputs:
        # - Two duplicates on Aug 17 (command must cancel the extra).
        # - One active event on a wrong date (Aug 19) + one active event in the past (June 1).
        self.eden_dup_a = Event.objects.create(
            artist=self.eden_artist,
            name="eden dup A",
            date=_dt(2026, 8, 17, 19, 0),
            venue=VENUE_MENORA,
            venue_place=self.menora_venue,
            city="תל אביב",
            category="concert",
            status="פעיל",
            country="IL",
        )
        self.eden_dup_b = Event.objects.create(
            artist=self.eden_artist,
            name="eden dup B",
            date=_dt(2026, 8, 17, 20, 0),
            venue=VENUE_MENORA,
            venue_place=self.menora_venue,
            city="תל אביב",
            category="concert",
            status="פעיל",
            country="IL",
        )
        self.eden_wrong_date = Event.objects.create(
            artist=self.eden_artist,
            name="eden wrong date",
            date=_dt(2026, 8, 19, 21, 0),
            venue=VENUE_MENORA,
            venue_place=self.menora_venue,
            city="תל אביב",
            category="concert",
            status="פעיל",
            country="IL",
        )
        self.eden_past_active = Event.objects.create(
            artist=self.eden_artist,
            name="eden past active",
            date=_dt(2026, 6, 1, 21, 0),
            venue=VENUE_MENORA,
            venue_place=self.menora_venue,
            city="תל אביב",
            category="concert",
            status="פעיל",
            country="IL",
        )

        # Omer/Eyal past events to cancel.
        now = timezone.now()
        self.omer_past = Event.objects.create(
            artist=self.omer_artist,
            name="omer past",
            date=now - timezone.timedelta(days=30),
            venue="אחר",
            venue_place=None,
            city="תל אביב",
            category="concert",
            status="פעיל",
            country="IL",
        )
        self.eyal_past = Event.objects.create(
            artist=self.eyal_artist,
            name="eyal past",
            date=now - timezone.timedelta(days=15),
            venue="אחר",
            venue_place=None,
            city="תל אביב",
            category="concert",
            status="פעיל",
            country="IL",
        )
        # And future events that must remain active.
        self.omer_future = Event.objects.create(
            artist=self.omer_artist,
            name="omer future",
            date=now + timezone.timedelta(days=30),
            venue="אחר",
            venue_place=None,
            city="תל אביב",
            category="concert",
            status="פעיל",
            country="IL",
        )
        self.eyal_future = Event.objects.create(
            artist=self.eyal_artist,
            name="eyal future",
            date=now + timezone.timedelta(days=40),
            venue="אחר",
            venue_place=None,
            city="תל אביב",
            category="concert",
            status="פעיל",
            country="IL",
        )

        # Pe'er event (Caesarea) for ticket seeding.
        self.peer_event = Event.objects.create(
            artist=self.peer_artist,
            name="peer caesarea test",
            date=_dt(2026, 8, 22, 20, 30),
            venue="אחר",
            venue_place=self.caesarea_place,
            city="קיסריה",
            category="concert",
            status="פעיל",
            country="IL",
        )
        self.mor_event = Event.objects.create(
            artist=self.mor_artist,
            name="mor menora test",
            date=_dt(2026, 8, 13, 21, 0),
            venue=VENUE_MENORA,
            venue_place=self.menora_venue,
            city="תל אביב",
            category="concert",
            status="פעיל",
            country="IL",
        )
        self.checkout_artist = Artist.objects.create(name="אמן בדיקת Checkout א", category="music")
        self.checkout_event = Event.objects.create(
            artist=self.checkout_artist,
            name="checkout test show",
            date=_dt(2026, 9, 1, 20, 0),
            venue=VENUE_MENORA,
            venue_place=self.menora_venue,
            city="תל אביב",
            category="concert",
            status="פעיל",
            country="IL",
        )

    def _assert_tiered_prices_match_section(self, tickets):
        for t in tickets:
            price = int(t.asking_price)
            section = t.custom_section_text or ""
            section_lower = section.lower()
            if "אורקסטרה" in section or "vip" in section_lower:
                self.assertIn(price, PREMIUM_PRICES_ILS)
            elif "תחתון" in section or "lower" in section_lower:
                self.assertIn(price, HIGH_PRICES_ILS)
            elif "אמצע" in section:
                self.assertIn(price, MID_PRICES_ILS)
            elif "עליון" in section or "upper" in section_lower:
                self.assertIn(price, BASE_PRICES_ILS)
            else:
                self.assertIn(price, FALLBACK_PRICES_ILS)

    def test_seed_dummy_tickets_idempotent_and_correct(self):
        # First run.
        call_command("seed_dummy_tickets", random_seed=123)

        seed_user = User.objects.get(username=SYSTEM_SEED_USERNAME)

        # 1) Eden Menora schedule must be exactly 3 active events on the target dates.
        eden_menora_active = list(
            Event.objects.filter(artist__name=EDEN, venue=VENUE_MENORA, status="פעיל").order_by("date")
        )
        self.assertEqual(len(eden_menora_active), 3)
        eden_dates = [ev.date.astimezone(TZ_IL).date() for ev in eden_menora_active]
        self.assertEqual(eden_dates, [_dt(2026, 8, 17, 21).date(), _dt(2026, 8, 18, 21).date(), _dt(2026, 8, 20, 21).date()])

        # 2) Past/wrong Eden events must be canceled.
        for ev in [self.eden_wrong_date, self.eden_past_active]:
            ev.refresh_from_db()
            self.assertNotEqual(ev.status, "פעיל")

        # Exactly one of the two Aug 17 duplicates must remain active.
        self.eden_dup_a.refresh_from_db()
        self.eden_dup_b.refresh_from_db()
        dup_a_is_active = self.eden_dup_a.status == "פעיל"
        dup_b_is_active = self.eden_dup_b.status == "פעיל"
        self.assertNotEqual(dup_a_is_active, dup_b_is_active)

        # 3) Omer Adam / Eyal Golan are untouched by dummy-ticket seeding.
        self.omer_past.refresh_from_db()
        self.eyal_past.refresh_from_db()
        self.omer_future.refresh_from_db()
        self.eyal_future.refresh_from_db()
        self.assertEqual(self.omer_past.status, 'פעיל')
        self.assertEqual(self.eyal_past.status, 'פעיל')
        self.assertEqual(self.omer_future.status, 'פעיל')
        self.assertEqual(self.eyal_future.status, 'פעיל')

        # 4) Seeded tickets exist for the 3 Eden events and have correct section/price/group constraints.
        eden_event_ids = [ev.id for ev in eden_menora_active]
        eden_tickets = Ticket.objects.filter(seller=seed_user, event_id__in=eden_event_ids, status="active")
        self.assertGreater(eden_tickets.count(), 0)
        self.assertTrue(all(int(t.asking_price) in ALL_ALLOWED_PRICES_ILS for t in eden_tickets))
        self._assert_tiered_prices_match_section(eden_tickets)

        for ev in eden_menora_active:
            tickets = list(Ticket.objects.filter(seller=seed_user, event=ev, status="active"))
            self.assertGreater(len(tickets), 0)

            sections = {t.custom_section_text for t in tickets}
            self.assertTrue(sections.issubset(set(MENORA_SECTION_IDS)))
            self.assertGreaterEqual(len(sections), 1)
            self.assertLessEqual(len(sections), 3)

            # Validate group sizing (listing_group_id): each group must be 2-4 tickets.
            groups = {}
            for t in tickets:
                groups.setdefault(t.listing_group_id, 0)
                groups[t.listing_group_id] += 1
            self.assertGreaterEqual(len(groups), 1)
            self.assertLessEqual(len(groups), 3)
            for _, group_size in groups.items():
                self.assertIn(group_size, {2, 3, 4})

        # 5) Pe'er event seeded with correct Caesarea section IDs & prices.
        peer_event = Event.objects.get(id=self.peer_event.id)
        peer_tickets = list(Ticket.objects.filter(seller=seed_user, event=peer_event, status="active"))
        self.assertGreater(len(peer_tickets), 0)
        self.assertTrue(all(int(t.asking_price) in ALL_ALLOWED_PRICES_ILS for t in peer_tickets))
        self._assert_tiered_prices_match_section(peer_tickets)

        peer_sections = {t.custom_section_text for t in peer_tickets}
        self.assertTrue(peer_sections.issubset(set(CAESAREA_SECTION_IDS)))
        self.assertGreaterEqual(len(peer_sections), 1)
        self.assertLessEqual(len(peer_sections), 3)

        peer_groups = {}
        for t in peer_tickets:
            peer_groups.setdefault(t.listing_group_id, 0)
            peer_groups[t.listing_group_id] += 1
        self.assertGreaterEqual(len(peer_groups), 1)
        self.assertLessEqual(len(peer_groups), 3)
        for _, group_size in peer_groups.items():
            self.assertIn(group_size, {2, 3, 4})

        # 6) Ben Tzur Caesarea events created and seeded with anchor pricing.
        ben_tzur_artist = Artist.objects.get(name=BEN_TZUR)
        self.assertEqual(ben_tzur_artist.category, "music")

        ben_events = list(
            Event.objects.filter(
                artist=ben_tzur_artist,
                status="פעיל",
                venue_place=self.caesarea_place,
            ).order_by("date")
        )
        self.assertEqual(len(ben_events), 2)
        ben_dates = [ev.date.astimezone(TZ_IL).date() for ev in ben_events]
        self.assertEqual(
            ben_dates,
            [_dt(2026, 7, 26, 21).date(), _dt(2026, 7, 27, 21).date()],
        )
        self.assertTrue(all(ev.high_demand for ev in ben_events))

        ben_tickets = list(
            Ticket.objects.filter(seller=seed_user, event__in=ben_events, status="active")
        )
        self.assertGreater(len(ben_tickets), 0)
        self.assertTrue(all(int(t.asking_price) in ALL_ALLOWED_PRICES_ILS for t in ben_tickets))
        self._assert_tiered_prices_match_section(ben_tickets)
        ben_sections = {t.custom_section_text for t in ben_tickets}
        self.assertTrue(ben_sections.issubset(set(CAESAREA_SECTION_IDS)))

        # 7) Mor Rabaie Menora events are seeded with Menora section ids and tiered prices.
        mor_tickets = list(Ticket.objects.filter(seller=seed_user, event=self.mor_event, status="active"))
        self.assertGreater(len(mor_tickets), 0)
        self.assertTrue(all(int(t.asking_price) in ALL_ALLOWED_PRICES_ILS for t in mor_tickets))
        self._assert_tiered_prices_match_section(mor_tickets)
        mor_sections = {t.custom_section_text for t in mor_tickets}
        self.assertTrue(mor_sections.issubset(set(MENORA_SECTION_IDS)))

        # 8) Checkout test artists are auto-scrubbed from DB.
        self.assertFalse(Artist.objects.filter(name__icontains="checkout").exists())
        self.assertFalse(Event.objects.filter(name__icontains="checkout").exists())

        # 9) Idempotency: running again must not grow ticket count.
        ticket_count_after_first = Ticket.objects.filter(seller=seed_user).count()
        call_command("seed_dummy_tickets", random_seed=123)
        self.assertEqual(Ticket.objects.filter(seller=seed_user).count(), ticket_count_after_first)

