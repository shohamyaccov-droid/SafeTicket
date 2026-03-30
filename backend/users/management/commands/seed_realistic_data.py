"""
Seed the database with realistic events, artists, and active ticket inventory (no lorem ipsum).

Uses real public figures and teams; images are fetched from Unsplash / Wikimedia Commons.

Usage:
  cd backend
  python manage.py seed_realistic_data
  python manage.py seed_realistic_data --reset

--reset removes all tickets owned by the demo seller used by this command (safe for overlapping DBs).

Requires: requests (see requirements.txt). Set DATABASE_URL / USE_CLOUDINARY as for normal runs.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import requests
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from users.models import Artist, Event, Ticket

User = get_user_model()

SELLER_EMAIL = 'seed_realistic_seller@safeticket.demo'

UA = {'User-Agent': 'TixTrade-Seed/1.1 (+https://github.com)'}


def _pdf(name: str = 'demo.pdf') -> ContentFile:
    body = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
    return ContentFile(body, name=name)


def _download_media(cmd: BaseCommand | None, instance, field_name: str, url: str) -> None:
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
        fname = f'seed_{field_name}_{instance.pk or "new"}.{ext}'
        field.save(fname, ContentFile(r.content), save=True)
    except Exception as ex:
        if cmd:
            cmd.stdout.write(cmd.style.WARNING(f'  skip {field_name} for {instance}: {ex}'))


# --- Realistic seed entities (names + image URLs) ---
ARTISTS = [
    {
        'name': 'עומר אדם',
        'genre': 'Pop',
        'description': 'זמר ויוצר — אחד האמנים המובילים בישראל.',
        'image': 'https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?auto=format&w=900&q=80',
    },
    {
        'name': 'Coldplay',
        'genre': 'Rock',
        'description': 'British rock band — worldwide tours.',
        'image': 'https://images.unsplash.com/photo-1540039155733-5bb30b53aa88?auto=format&w=900&q=80',
    },
    {
        'name': 'Taylor Swift',
        'genre': 'Pop',
        'description': 'Singer-songwriter — The Eras Tour.',
        'image': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&w=900&q=80',
    },
    {
        'name': 'שלמה ארצי',
        'genre': 'Pop / Rock',
        'description': 'זמר ומלחין ישראלי.',
        'image': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/29/Shlomo_Artzi.JPG/640px-Shlomo_Artzi.JPG',
    },
    {
        'name': 'Bruno Mars',
        'genre': 'R&B / Pop',
        'description': 'Singer, songwriter, and performer.',
        'image': 'https://images.unsplash.com/photo-1598387993441-a364f854c3f3?auto=format&w=900&q=80',
    },
    {
        'name': 'מכבי תל אביב',
        'genre': 'ספורט',
        'description': 'מועדון כדורסל וכדורגל — תל אביב.',
        'image': 'https://images.unsplash.com/photo-1546519638-68e109498ffc?auto=format&w=900&q=80',
    },
    {
        'name': 'ריאל מדריד',
        'genre': 'כדורגל',
        'description': 'מועדון הכדורגל ריאל מדריד.',
        'image': 'https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&w=900&q=80',
    },
    {
        'name': 'ברצלונה',
        'genre': 'כדורגל',
        'description': 'מועדון הכדורגל ברצלונה.',
        'image': 'https://images.unsplash.com/photo-1431324155629-1a6deb1dec8d?auto=format&w=900&q=80',
    },
    {
        'name': 'אדיר מילר',
        'genre': 'סטנדאפ',
        'description': 'שחקן וקומיקאי ישראלי.',
        'image': 'https://images.unsplash.com/photo-1585699324551-f6c309eedeca?auto=format&w=900&q=80',
    },
    {
        'name': 'שחר חסון',
        'genre': 'סטנדאפ',
        'description': 'סטנדאפיסט ויוצר ישראלי.',
        'image': 'https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&w=900&q=80',
    },
    {
        'name': 'האמילטון — מחזמר',
        'genre': 'מחזמר',
        'description': 'המחזמר האמילטון — הופעות ברחבי העולם.',
        'image': 'https://images.unsplash.com/photo-1503095396549-807759245b35?auto=format&w=900&q=80',
    },
    {
        'name': 'מלך האריות — מחזמר',
        'genre': 'מחזמר',
        'description': 'The Lion King — מחזמר מבית דיסני.',
        'image': 'https://images.unsplash.com/photo-1514306197117-bf71f1cc5968?auto=format&w=900&q=80',
    },
]


def _event_specs(now):
    """(artist_name, event fields + ticket rows)."""
    d = lambda days, h=20, m=0: now + timedelta(days=days, hours=h, minutes=m)
    return [
        {
            'artist': 'עומר אדם',
            'name': 'עומר אדם — הופעה בפארק הירקון',
            'date': d(14, 20, 30),
            'venue': 'אחר',
            'city': 'תל אביב-יפו',
            'category': 'concert',
            'image': 'https://images.unsplash.com/photo-1429962714451-bb934ecdc4ec?auto=format&w=1200&q=80',
            'tickets': [(Decimal('420'), 'A12', 4), (Decimal('380'), 'A13', 3)],
        },
        {
            'artist': 'Coldplay',
            'name': 'Coldplay — Music Of The Spheres',
            'date': d(32, 19, 0),
            'venue': 'מנורה מבטחים',
            'city': 'תל אביב-יפו',
            'category': 'concert',
            'image': 'https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&w=1200&q=80',
            'tickets': [(Decimal('890'), 'B5', 6), (Decimal('750'), 'B6', 5)],
        },
        {
            'artist': 'Taylor Swift',
            'name': 'Taylor Swift — The Eras Tour',
            'date': d(48, 19, 30),
            'venue': 'סמי עופר',
            'city': 'חיפה',
            'category': 'concert',
            'image': 'https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?auto=format&w=1200&q=80',
            'tickets': [(Decimal('1250'), 'VIP1', 2), (Decimal('980'), 'C20', 4), (Decimal('820'), 'C21', 3)],
        },
        {
            'artist': 'שלמה ארצי',
            'name': 'שלמה ארצי — מופע קיץ',
            'date': d(21, 21, 0),
            'venue': 'בלומפילד',
            'city': 'תל אביב-יפו',
            'category': 'concert',
            'image': 'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&w=1200&q=80',
            'tickets': [(Decimal('310'), 'D8', 5), (Decimal('280'), 'D9', 4)],
        },
        {
            'artist': 'Bruno Mars',
            'name': 'Bruno Mars — Live in Tel Aviv',
            'date': d(58, 20, 0),
            'venue': 'מנורה מבטחים',
            'city': 'תל אביב-יפו',
            'category': 'concert',
            'image': 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa9f?auto=format&w=1200&q=80',
            'tickets': [(Decimal('560'), 'E3', 5)],
        },
        {
            'artist': 'מכבי תל אביב',
            'name': 'יורוליג: מכבי תל אביב נגד ברצלונה',
            'date': d(9, 21, 5),
            'venue': 'מנורה מבטחים',
            'city': 'תל אביב-יפו',
            'category': 'sport',
            'home_team': 'מכבי תל אביב',
            'away_team': 'ברצלונה',
            'tournament': 'יורוליג',
            'image': 'https://images.unsplash.com/photo-1519861537743-0d973a40d389?auto=format&w=1200&q=80',
            'tickets': [(Decimal('220'), 'G1', 6), (Decimal('190'), 'G2', 8)],
        },
        {
            'artist': 'מכבי תל אביב',
            'name': 'ליגת העל: מכבי תל אביב נגד הפועל באר שבע',
            'date': d(11, 20, 30),
            'venue': 'בלומפילד',
            'city': 'תל אביב-יפו',
            'category': 'sport',
            'home_team': 'מכבי תל אביב',
            'away_team': 'הפועל באר שבע',
            'tournament': 'ליגת העל',
            'image': 'https://images.unsplash.com/photo-1579952363873-27f3bade9f55?auto=format&w=1200&q=80',
            'tickets': [(Decimal('140'), 'H10', 10), (Decimal('120'), 'H11', 12)],
        },
        {
            'artist': 'ריאל מדריד',
            'name': 'ליגת האלופות: ריאל מדריד נגד ליברפול',
            'date': d(25, 21, 0),
            'venue': 'סמי עופר',
            'city': 'חיפה',
            'category': 'sport',
            'home_team': 'ריאל מדריד',
            'away_team': 'ליברפול',
            'tournament': 'UEFA Champions League',
            'image': 'https://images.unsplash.com/photo-1489944440615-453fc2b6a9a9?auto=format&w=1200&q=80',
            'tickets': [(Decimal('480'), 'CL1', 3), (Decimal('410'), 'CL2', 4)],
        },
        {
            'artist': 'ברצלונה',
            'name': 'ליגת האלופות: ברצלונה נגד באיירן מינכן',
            'date': d(36, 20, 45),
            'venue': 'מנורה מבטחים',
            'city': 'תל אביב-יפו',
            'category': 'sport',
            'home_team': 'ברצלונה',
            'away_team': 'באיירן מינכן',
            'tournament': 'UEFA Champions League',
            'image': 'https://images.unsplash.com/photo-1522778119026-d647f0596c20?auto=format&w=1200&q=80',
            'tickets': [(Decimal('520'), 'CL3', 4)],
        },
        {
            'artist': 'אדיר מילר',
            'name': 'אדיר מילר — מופע סטנדאפ',
            'date': d(12, 19, 30),
            'venue': 'בארבי תל אביב',
            'city': 'תל אביב-יפו',
            'category': 'standup',
            'image': 'https://images.unsplash.com/photo-1585699324551-f6c309eedeca?auto=format&w=1200&q=80',
            'tickets': [(Decimal('180'), 'S1', 6), (Decimal('165'), 'S2', 5)],
        },
        {
            'artist': 'שחר חסון',
            'name': 'שחר חסון — הרצאה וסטנדאפ',
            'date': d(17, 20, 0),
            'venue': 'מנורה מבטחים',
            'city': 'תל אביב-יפו',
            'category': 'standup',
            'image': 'https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&w=1200&q=80',
            'tickets': [(Decimal('160'), 'S9', 8)],
        },
        {
            'artist': 'האמילטון — מחזמר',
            'name': 'האמילטון — המחזמר (תל אביב)',
            'date': d(42, 19, 0),
            'venue': 'מנורה מבטחים',
            'city': 'תל אביב-יפו',
            'category': 'theater',
            'image': 'https://images.unsplash.com/photo-1503095396549-807759245b35?auto=format&w=1200&q=80',
            'tickets': [(Decimal('290'), 'T1', 4), (Decimal('240'), 'T2', 5)],
        },
        {
            'artist': 'מלך האריות — מחזמר',
            'name': 'מלך האריות — המחזמר המקורי',
            'date': d(55, 18, 0),
            'venue': 'סמי עופר',
            'city': 'חיפה',
            'category': 'theater',
            'image': 'https://images.unsplash.com/photo-1514306197117-bf71f1cc5968?auto=format&w=1200&q=80',
            'tickets': [(Decimal('320'), 'L10', 5), (Decimal('260'), 'L11', 6)],
        },
    ]


class Command(BaseCommand):
    help = 'Seed realistic artists, events, and active tickets (Viagogo-style demo data).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete all tickets listed by the realistic-seed seller before seeding.',
        )

    def handle(self, *args, **options):
        if options['reset']:
            u = User.objects.filter(email=SELLER_EMAIL).first()
            if u:
                n = Ticket.objects.filter(seller=u).delete()[0]
                self.stdout.write(self.style.WARNING(f'Removed {n} ticket row(s) for {SELLER_EMAIL}.'))

        seller, _ = User.objects.get_or_create(
            email=SELLER_EMAIL,
            defaults={
                'username': 'realistic_seed_seller',
                'role': 'seller',
                'is_email_verified': True,
            },
        )
        seller.set_password('RealisticSeed123!')
        seller.role = 'seller'
        seller.save()

        artists_by_name: dict[str, Artist] = {}
        for row in ARTISTS:
            artist, _ = Artist.objects.update_or_create(
                name=row['name'],
                defaults={
                    'description': row['description'],
                    'genre': row['genre'],
                },
            )
            _download_media(self, artist, 'image', row['image'])
            artists_by_name[row['name']] = artist
            self.stdout.write(self.style.SUCCESS(f'Artist OK: {artist.name}'))

        now = timezone.now()
        for spec in _event_specs(now):
            artist = artists_by_name.get(spec['artist'])
            if not artist:
                self.stdout.write(self.style.ERROR(f"Missing artist: {spec['artist']}"))
                continue
            defaults = {
                'artist': artist,
                'venue': spec['venue'],
                'city': spec['city'],
                'category': spec['category'],
                'status': 'פעיל',
                'home_team': spec.get('home_team') or None,
                'away_team': spec.get('away_team') or None,
                'tournament': spec.get('tournament') or None,
            }
            ev, created = Event.objects.update_or_create(
                name=spec['name'],
                date=spec['date'],
                defaults=defaults,
            )
            _download_media(self, ev, 'image', spec['image'])
            action = 'created' if created else 'updated'
            self.stdout.write(self.style.NOTICE(f'Event {action}: {ev.name}'))

            for price, seat_key, qty in spec['tickets']:
                if Ticket.objects.filter(event=ev, seller=seller, seat_row=seat_key).exists():
                    continue
                t = Ticket(
                    seller=seller,
                    event=ev,
                    event_name=ev.name,
                    event_date=ev.date,
                    venue=ev.get_venue_display(),
                    original_price=price,
                    available_quantity=qty,
                    verification_status='מאומת',
                    status='active',
                    listing_group_id=str(uuid.uuid4()),
                    ticket_type='כרטיס אלקטרוני / PDF',
                    split_type='כל כמות',
                    seat_row=seat_key,
                    pdf_file=_pdf(name=f'realistic_{ev.id}_{seat_key}.pdf'),
                )
                t.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ticket id={t.id} ₪{price} qty={qty} row={seat_key}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                '\nDone.\n'
                f'  Demo seller: {SELLER_EMAIL} / RealisticSeed123!\n'
                '  Each event has active tickets with available_quantity > 0.\n'
            )
        )
