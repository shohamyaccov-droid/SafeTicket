"""
Seed Viagogo-style catalog for homepage discovery (performers, venues, events, tickets).

Schema mapping (no separate Category/Performer models):
  - Category labels → Event.category (concert | sport | standup | theater)
  - Performer → Artist
  - Venue → users.Venue (+ Event.venue legacy label + venue_place FK)

Usage:
  cd backend
  python manage.py seed_viagogo_data
  python manage.py seed_viagogo_data --skip-images
"""
from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import requests
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from users.models import Artist, Event, Ticket, Venue

User = get_user_model()

TZ_IL = ZoneInfo('Asia/Jerusalem')
SELLER_EMAIL = 'seed_viagogo@safeticket.demo'

VENUE_LEGACY_ISRAEL = 'ישראל'
VENUE_BLOOMFIELD_CONCERTS = 'אצטדיון בלומפילד (הופעות)'

# Homepage category labels (mapped to Event.category in DB)
CATEGORIES = {
    'Concerts': 'concert',
    'Sports': 'sport',
    'Comedy': 'standup',
    'Theatre': 'theater',
}

UA = {'User-Agent': 'TradeTix-ViagogoSeed/1.0 (+https://github.com)'}

IMAGE_URLS = {
    'concert': 'https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&w=1200&q=80',
    'singer': 'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&w=1200&q=80',
    'pop_il': 'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&w=1200&q=80',
    'basketball': 'https://images.unsplash.com/photo-1546519638-68e109498ffc?auto=format&w=1200&q=80',
    'standup': 'https://images.unsplash.com/photo-1585699324551-f6c309eedeca?auto=format&w=1200&q=80',
    'theatre': 'https://images.unsplash.com/photo-1503095396549-807759245b35?auto=format&w=1200&q=80',
    'stadium': 'https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&w=1200&q=80',
}


def _pdf(name: str = 'viagogo.pdf') -> ContentFile:
    return ContentFile(
        b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n',
        name=name,
    )


def _dt(y: int, m: int, d: int, h: int = 20, minute: int = 15) -> datetime:
    return datetime(y, m, d, h, minute, 0, tzinfo=TZ_IL)


def _days_from_now(days: int, h: int = 20, minute: int = 30) -> datetime:
    """Event datetime N days ahead (Israel) — powers Last Minute / הדקה ה-90 row."""
    local_now = timezone.localtime(timezone.now())
    target_day = (local_now + timedelta(days=days)).date()
    naive = datetime.combine(target_day, time(h, minute))
    return timezone.make_aware(naive, TZ_IL)


def _download_media(cmd: BaseCommand, instance, field_name: str, url: str) -> None:
    field = getattr(instance, field_name)
    if field and field.name:
        return
    try:
        r = requests.get(url, timeout=30, headers=UA)
        r.raise_for_status()
        ext = 'jpg'
        ct = (r.headers.get('content-type') or '').lower()
        if 'png' in ct:
            ext = 'png'
        elif 'webp' in ct:
            ext = 'webp'
        fname = f'viagogo_{field_name}_{instance.pk or "new"}.{ext}'
        field.save(fname, ContentFile(r.content), save=True)
    except Exception as ex:
        cmd.stdout.write(cmd.style.WARNING(f'  skip image {field_name}: {ex}'))


class Command(BaseCommand):
    help = 'Seed Viagogo-inspired Israeli catalog (artists, venues, events, tickets) for homepage UI.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-images',
            action='store_true',
            help='Do not download Unsplash placeholder images.',
        )

    def handle(self, *args, **options):
        skip_images = options['skip_images']
        now = timezone.now()
        self.stdout.write(self.style.NOTICE(f'Seeding from {now.isoformat()}'))

        venues = self._seed_venues()
        artists = self._seed_artists(cmd=self, skip_images=skip_images)
        seller = self._get_seller()

        stats = {'events_created': 0, 'events_updated': 0, 'tickets': 0}

        with transaction.atomic():
            stats = self._seed_all_events(
                venues=venues,
                artists=artists,
                seller=seller,
                cmd=self,
                skip_images=skip_images,
                stats=stats,
            )

        self.stdout.write(self.style.SUCCESS('\nViagogo seed complete.'))
        self.stdout.write(f'  Categories: {", ".join(CATEGORIES.keys())}')
        self.stdout.write(
            f'  Events: {stats["events_created"]} created, {stats["events_updated"]} updated'
        )
        self.stdout.write(f'  Tickets: {stats["tickets"]} new listing(s)')
        self.stdout.write(f'  Seller: {SELLER_EMAIL} (password set on each run)')

    def _seed_venues(self) -> dict[str, Venue]:
        rows = [
            ('אצטדיון רמת גן', 'תל אביב'),
            ('אצטדיון בלומפילד', 'תל אביב'),
            ('זאפה אמפי שוני', 'בנימינה'),
            ('אמפי קיסריה', 'קיסריה'),
            ('תיאטרון ירושלים', 'ירושלים'),
            ('היכל הקריה', 'אשדוד'),
            ('זאפה לייב פארק', 'ראשון לציון'),
        ]
        out = {}
        for name, city in rows:
            v, _ = Venue.objects.get_or_create(name=name, city=city)
            out[name] = v
            self.stdout.write(self.style.SUCCESS(f'Venue: {name}, {city}'))
        return out

    def _seed_artists(self, *, cmd: BaseCommand, skip_images: bool) -> dict[str, Artist]:
        specs = [
            ('עומר אדם', 'Pop', CATEGORIES['Concerts'], IMAGE_URLS['singer']),
            ('אייל גולן', 'Mizrahi', CATEGORIES['Concerts'], IMAGE_URLS['singer']),
            ('שלמה ארצי', 'Rock / Pop', CATEGORIES['Concerts'], IMAGE_URLS['pop_il']),
            ('אישי ריבו', 'Pop', CATEGORIES['Concerts'], IMAGE_URLS['singer']),
            ('עדן חסון', 'Pop', CATEGORIES['Concerts'], IMAGE_URLS['singer']),
            ('אדיר מילר', 'Comedy', CATEGORIES['Comedy'], IMAGE_URLS['standup']),
            ('צלילי המוזיקה', 'Musical', CATEGORIES['Theatre'], IMAGE_URLS['theatre']),
        ]
        out = {}
        for name, genre, _cat, img in specs:
            artist, _ = Artist.objects.update_or_create(
                name=name,
                defaults={'genre': genre, 'description': f'{name} — Viagogo-style seed'},
            )
            if not skip_images:
                _download_media(cmd, artist, 'image', img)
            out[name] = artist
        return out

    def _get_seller(self) -> User:
        seller, _ = User.objects.update_or_create(
            email=SELLER_EMAIL,
            defaults={
                'username': 'viagogo_seed_seller',
                'role': 'seller',
                'is_email_verified': True,
            },
        )
        seller.password = make_password('ViagogoSeed123!')
        seller.role = 'seller'
        seller.save(update_fields=['password', 'role', 'is_email_verified', 'updated_at'])
        return seller

    def _upsert_event(
        self,
        *,
        artist: Artist | None,
        when: datetime,
        name: str,
        venue_label: str,
        venue_place: Venue | None,
        city: str,
        category: str,
        high_demand: bool = False,
        home_team: str | None = None,
        away_team: str | None = None,
        tournament: str | None = None,
        image_url: str | None = None,
        cmd: BaseCommand,
        skip_images: bool,
        stats: dict,
    ) -> Event:
        lookup = {'date': when}
        if artist:
            lookup['artist'] = artist
        else:
            lookup['name'] = name

        defaults = {
            'name': name,
            'artist': artist,
            'venue': venue_label,
            'venue_place': venue_place,
            'city': city,
            'category': category,
            'status': 'פעיל',
            'country': 'IL',
            'high_demand': high_demand,
            'home_team': home_team,
            'away_team': away_team,
            'tournament': tournament,
        }
        ev, created = Event.objects.update_or_create(**lookup, defaults=defaults)

        if image_url and not skip_images:
            _download_media(cmd, ev, 'image', image_url)

        if created:
            stats['events_created'] += 1
            self.stdout.write(self.style.SUCCESS(f'  + event: {name} @ {when.date()}'))
        else:
            stats['events_updated'] += 1
            self.stdout.write(self.style.NOTICE(f'  ~ event: {name} @ {when.date()}'))
        return ev

    def _add_tickets(
        self,
        ev: Event,
        seller: User,
        rows: list[tuple[Decimal, str, int]],
        stats: dict,
    ) -> None:
        for price, seat_row, qty in rows:
            if Ticket.objects.filter(event=ev, seller=seller, seat_row=seat_row).exists():
                continue
            t = Ticket(
                seller=seller,
                event=ev,
                event_name=ev.name,
                event_date=ev.date,
                venue=ev.get_venue_display() if hasattr(ev, 'get_venue_display') else ev.venue,
                original_price=price,
                asking_price=price,
                available_quantity=qty,
                verification_status='מאומת',
                status='active',
                listing_group_id=str(uuid.uuid4()),
                ticket_type='כרטיס אלקטרוני / PDF',
                split_type='כל כמות',
                seat_row=seat_row,
                pdf_file=_pdf(name=f'viagogo_{ev.id}_{seat_row}.pdf'),
            )
            t.save()
            stats['tickets'] += 1

    def _seed_all_events(
        self,
        *,
        venues: dict[str, Venue],
        artists: dict[str, Artist],
        seller: User,
        cmd: BaseCommand,
        skip_images: bool,
        stats: dict,
    ) -> dict:
        ramat = venues['אצטדיון רמת גן']
        bloomfield = venues['אצטדיון בלומפילד']
        zappa_shuni = venues['זאפה אמפי שוני']
        caesarea = venues['אמפי קיסריה']
        jlm_theatre = venues['תיאטרון ירושלים']
        hakirya = venues['היכל הקריה']
        zappa_park = venues['זאפה לייב פארק']

        omer = artists['עומר אדם']
        omer_dates = [
            (_dt(2026, 6, 9), True),
            (_dt(2026, 6, 10), True),
            (_dt(2026, 6, 11), True),
            (_dt(2026, 6, 15), False),  # waitlist — high_demand, 0 tickets
            (_dt(2026, 6, 16), True),
        ]
        for when, with_tickets in omer_dates:
            title = f'עומר אדם - אצטדיון רמת גן — {when.strftime("%d.%m.%Y")}'
            ev = self._upsert_event(
                artist=omer,
                when=when,
                name=title,
                venue_label=VENUE_LEGACY_ISRAEL,
                venue_place=ramat,
                city='תל אביב',
                category=CATEGORIES['Concerts'],
                high_demand=not with_tickets,
                image_url=IMAGE_URLS['stadium'],
                cmd=cmd,
                skip_images=skip_images,
                stats=stats,
            )
            if with_tickets:
                self._add_tickets(
                    ev,
                    seller,
                    [
                        (Decimal('249'), '12', 4),
                        (Decimal('319'), '8', 3),
                        (Decimal('399'), 'VIP', 2),
                    ],
                    stats,
                )
            else:
                Ticket.objects.filter(event=ev).delete()

        eyal = artists['אייל גולן']
        for day in (11, 13, 14, 18):
            when = _dt(2026, 6, day, 20, 30)
            title = f'אייל גולן - אצטדיון בלומפילד — {when.strftime("%d.%m.%Y")}'
            ev = self._upsert_event(
                artist=eyal,
                when=when,
                name=title,
                venue_label=VENUE_BLOOMFIELD_CONCERTS,
                venue_place=bloomfield,
                city='תל אביב',
                category=CATEGORIES['Concerts'],
                high_demand=True,
                image_url=IMAGE_URLS['stadium'],
                cmd=cmd,
                skip_images=skip_images,
                stats=stats,
            )
            self._add_tickets(
                ev,
                seller,
                [
                    (Decimal('229'), '201', 5),
                    (Decimal('269'), '214', 4),
                    (Decimal('299'), '301', 3),
                ],
                stats,
            )

        artzi = artists['שלמה ארצי']
        artzi_shows = [
            (_dt(2026, 6, 13), zappa_shuni, 'בנימינה', 'שלמה ארצי - זאפה אמפי שוני'),
            (_dt(2026, 7, 9), caesarea, 'קיסריה', 'שלמה ארצי - אמפי קיסריה'),
        ]
        for when, vp, city, title in artzi_shows:
            ev = self._upsert_event(
                artist=artzi,
                when=when,
                name=f'{title} — {when.strftime("%d.%m.%Y")}',
                venue_label=VENUE_LEGACY_ISRAEL,
                venue_place=vp,
                city=city,
                category=CATEGORIES['Concerts'],
                image_url=IMAGE_URLS['pop_il'],
                cmd=cmd,
                skip_images=skip_images,
                stats=stats,
            )
            self._add_tickets(ev, seller, [(Decimal('310'), 'A', 6), (Decimal('360'), 'B', 4)], stats)

        ribo = artists['אישי ריבו']
        for day in (8, 17):
            when = _dt(2026, 6, day, 20, 45)
            title = f'אישי ריבו - זאפה אמפי שוני — {when.strftime("%d.%m.%Y")}'
            ev = self._upsert_event(
                artist=ribo,
                when=when,
                name=title,
                venue_label=VENUE_LEGACY_ISRAEL,
                venue_place=zappa_shuni,
                city='בנימינה',
                category=CATEGORIES['Concerts'],
                image_url=IMAGE_URLS['singer'],
                cmd=cmd,
                skip_images=skip_images,
                stats=stats,
            )
            self._add_tickets(ev, seller, [(Decimal('279'), '1', 5), (Decimal('329'), '2', 3)], stats)

        eden = artists['עדן חסון']
        when_eden = _dt(2026, 6, 25, 21, 0)
        ev_eden = self._upsert_event(
            artist=eden,
            when=when_eden,
            name=f'עדן חסון - זאפה לייב פארק — {when_eden.strftime("%d.%m.%Y")}',
            venue_label=VENUE_LEGACY_ISRAEL,
            venue_place=zappa_park,
            city='ראשון לציון',
            category=CATEGORIES['Concerts'],
            image_url=IMAGE_URLS['concert'],
            cmd=cmd,
            skip_images=skip_images,
            stats=stats,
        )
        self._add_tickets(ev_eden, seller, [(Decimal('199'), 'P1', 8), (Decimal('249'), 'P2', 5)], stats)

        # Last minute — 1–2 days from now
        miller = artists['אדיר מילר']
        when_miller = _days_from_now(1, 20, 0)
        ev_miller = self._upsert_event(
            artist=miller,
            when=when_miller,
            name=f'אדיר מילר - תיאטרון ירושלים — {when_miller.strftime("%d.%m.%Y")}',
            venue_label=VENUE_LEGACY_ISRAEL,
            venue_place=jlm_theatre,
            city='ירושלים',
            category=CATEGORIES['Comedy'],
            image_url=IMAGE_URLS['standup'],
            cmd=cmd,
            skip_images=skip_images,
            stats=stats,
        )
        self._add_tickets(ev_miller, seller, [(Decimal('149'), 'C1', 10), (Decimal('179'), 'C2', 8)], stats)

        when_sport = _days_from_now(2, 19, 30)
        ev_sport = self._upsert_event(
            artist=None,
            when=when_sport,
            name=f'מכבי אשדוד נגד הפועל חולון — {when_sport.strftime("%d.%m.%Y")}',
            venue_label=VENUE_LEGACY_ISRAEL,
            venue_place=hakirya,
            city='אשדוד',
            category=CATEGORIES['Sports'],
            home_team='מכבי אשדוד',
            away_team='הפועל חולון',
            tournament='ליגת Winner',
            image_url=IMAGE_URLS['basketball'],
            cmd=cmd,
            skip_images=skip_images,
            stats=stats,
        )
        self._add_tickets(
            ev_sport,
            seller,
            [(Decimal('89'), '101', 12), (Decimal('120'), '102', 10)],
            stats,
        )

        sound = artists['צלילי המוזיקה']
        when_theatre = _dt(2026, 8, 14, 19, 0)
        ev_theatre = self._upsert_event(
            artist=sound,
            when=when_theatre,
            name=f'The Sound of Music — תיאטרון ירושלים — {when_theatre.strftime("%d.%m.%Y")}',
            venue_label=VENUE_LEGACY_ISRAEL,
            venue_place=jlm_theatre,
            city='ירושלים',
            category=CATEGORIES['Theatre'],
            image_url=IMAGE_URLS['theatre'],
            cmd=cmd,
            skip_images=skip_images,
            stats=stats,
        )
        self._add_tickets(
            ev_theatre,
            seller,
            [(Decimal('220'), 'T1', 6), (Decimal('280'), 'T2', 4)],
            stats,
        )

        self.stdout.write(
            self.style.WARNING(
                f'Last-minute row targets: Adir Miller @ {when_miller.date()}, '
                f'Maccabi Ashdod @ {when_sport.date()} (within 4 days of {timezone.localdate()})'
            )
        )
        return stats
