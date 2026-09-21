"""
Copyright-safe client catalog: wipe leftover artist/event images, then seed ONLY
the approved 2026 shows with blank image fields.

Usage:
  python manage.py seed_client_catalog --wipe   # delete all artists/events, then seed
  python manage.py seed_client_catalog          # strip images, prune extras, upsert list
  python manage.py seed_client_catalog --dry-run
"""
from __future__ import annotations

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import Artist, Event, Offer, Ticket, TicketAlert, Venue, VenueSection
from users.production_safety import refuse_destructive

TZ_IL = ZoneInfo('Asia/Jerusalem')

ALLOWED_ARTISTS = [
    'NEXT',
    'היסטריה',
    'ישי ריבו',
    'אזיליה בנקס',
    'מור',
    'איתי לוי',
    'נועם בתן',
]

IMAGE_STORAGE_PREFIXES = (
    'artists/images',
    'artist_covers',
    'events/images',
)

VENUE_MENORA = 'היכל מנורה מבטחים'
VENUE_PAIS = 'פיס ארנה ירושלים'
VENUE_GENERIC = 'ישראל'


def _il(year, month, day, hour=20, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=TZ_IL)


def _console(text: str) -> str:
    encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
    return str(text).encode(encoding, errors='replace').decode(encoding)


def _delete_filefield(field) -> bool:
    name = getattr(field, 'name', None) or ''
    if not str(name).strip():
        return False
    try:
        field.delete(save=False)
        return True
    except Exception:
        try:
            storage = field.storage
            if storage.exists(name):
                storage.delete(name)
                return True
        except Exception:
            return False
    return False


def _clear_instance_images(instance, field_names) -> int:
    cleared = 0
    update = []
    for fname in field_names:
        field = getattr(instance, fname, None)
        if field is None:
            continue
        if _delete_filefield(field):
            cleared += 1
        if getattr(instance, fname, None):
            setattr(instance, fname, None)
            update.append(fname)
    if update:
        instance.save(update_fields=update)
    return cleared


def _purge_storage_prefix(prefix: str) -> int:
    deleted = 0
    try:
        directories, files = default_storage.listdir(prefix)
    except Exception:
        return 0
    for filename in files:
        path = f'{prefix.rstrip("/")}/{filename}'
        try:
            default_storage.delete(path)
            deleted += 1
        except Exception:
            continue
    for directory in directories:
        deleted += _purge_storage_prefix(f'{prefix.rstrip("/")}/{directory}')
    return deleted


def _purge_local_media_dirs() -> int:
    """Remove leftover files under MEDIA_ROOT even if DB rows already point at empty fields."""
    from pathlib import Path

    media_root = Path(getattr(settings, 'MEDIA_ROOT', '') or '')
    if not media_root or not media_root.exists():
        return 0
    deleted = 0
    for rel in IMAGE_STORAGE_PREFIXES:
        folder = media_root / rel
        if not folder.exists():
            continue
        for path in folder.rglob('*'):
            if path.is_file():
                try:
                    path.unlink()
                    deleted += 1
                except OSError:
                    continue
    return deleted


class Command(BaseCommand):
    help = 'Reset marketplace catalog to the approved 2026 artist/event list with NO images.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Delete ALL artists/events (and cascaded tickets/alerts) before seeding.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print planned work without writing.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        wipe = options['wipe']

        if wipe and not dry_run:
            try:
                refuse_destructive('seed_client_catalog --wipe')
            except Exception as exc:
                raise CommandError(str(exc)) from exc

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] no database or storage writes'))

        with transaction.atomic():
            if wipe:
                self._wipe(dry_run)
            else:
                self._strip_all_images(dry_run)
                self._prune_extras(dry_run)

            if not dry_run:
                n_files = 0
                for prefix in IMAGE_STORAGE_PREFIXES:
                    n_files += _purge_storage_prefix(prefix)
                n_files += _purge_local_media_dirs()
                self.stdout.write(f'Purged leftover catalog image files: {n_files}')

            self._seed(dry_run)

        artists = list(Artist.objects.order_by('name').values_list('name', flat=True))
        events = Event.objects.count()
        imaged = (
            Artist.objects.exclude(image='').exclude(image__isnull=True).count()
            + Artist.objects.exclude(cover_image='').exclude(cover_image__isnull=True).count()
            + Event.objects.exclude(image='').exclude(image__isnull=True).count()
        )
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 56))
        self.stdout.write(_console(f'ARTIST COUNT: {len(artists)}'))
        for name in artists:
            self.stdout.write(_console(f'  - {name}'))
        self.stdout.write(_console(f'EVENT COUNT: {events}'))
        self.stdout.write(f'IMAGE FIELDS STILL SET: {imaged}')
        self.stdout.write(self.style.SUCCESS('=' * 56))
        if events != 21:
            raise CommandError(_console(f'Expected 21 events, got {events}'))
        if set(artists) != set(ALLOWED_ARTISTS):
            raise CommandError(
                _console(f'Artist set mismatch. expected={ALLOWED_ARTISTS} got={artists}')
            )
        if imaged:
            raise CommandError('Catalog still has image fields set — aborting.')

    def _wipe(self, dry_run: bool) -> None:
        n_artists = Artist.objects.count()
        n_events = Event.objects.count()
        n_tickets = Ticket.objects.count()
        n_offers = Offer.objects.count()
        n_alerts = TicketAlert.objects.count()
        self.stdout.write(
            f'Wipe catalog: artists={n_artists} events={n_events} '
            f'tickets={n_tickets} offers={n_offers} alerts={n_alerts}'
        )
        if dry_run:
            return
        self._strip_all_images(False)
        # Unmanaged SQL so a stale TicketAlert schema cannot block catalog wipe.
        from django.db import connection

        with connection.cursor() as cursor:
            tables = connection.introspection.table_names()
            if 'users_ticketalert_watched_events' in tables:
                cursor.execute('DELETE FROM users_ticketalert_watched_events')
            if 'users_ticketalert' in tables:
                cursor.execute('DELETE FROM users_ticketalert')
        Offer.objects.all().delete()
        Ticket.objects.all().delete()
        Event.objects.all().delete()
        Artist.objects.all().delete()

    def _strip_all_images(self, dry_run: bool) -> None:
        artists = list(Artist.objects.all())
        events = list(Event.objects.all())
        if dry_run:
            self.stdout.write(f'Would strip images on {len(artists)} artists and {len(events)} events')
            return
        cleared = 0
        for artist in artists:
            cleared += _clear_instance_images(artist, ('image', 'cover_image'))
        for event in events:
            cleared += _clear_instance_images(event, ('image',))
        self.stdout.write(f'Cleared {cleared} image file(s) from Artist/Event rows')

    def _prune_extras(self, dry_run: bool) -> None:
        extras = Artist.objects.exclude(name__in=ALLOWED_ARTISTS)
        names = list(extras.values_list('name', flat=True))
        if not names:
            return
        self.stdout.write(_console(f'Pruning extra artists ({len(names)}): {", ".join(names)}'))
        if dry_run:
            return
        extras.delete()

    def _seed(self, dry_run: bool) -> None:
        if dry_run:
            self.stdout.write('Would upsert the approved 7 artists and their events (no images).')
            return

        venues = {}

        def venue(name, city):
            key = (name, city)
            if key not in venues:
                venues[key], _ = Venue.objects.get_or_create(name=name, city=city)
            return venues[key]

        menora = venue(VENUE_MENORA, 'תל אביב')
        pais = venue(VENUE_PAIS, 'ירושלים')
        ramat_gan = venue('אצטדיון רמת גן', 'רמת גן')
        ampi_max = venue('אמפי MAX', 'ראשון לציון')
        ampi_tlv = venue('אמפי תל אביב', 'תל אביב')
        for section in ('עמידה', 'ישיבה'):
            VenueSection.objects.get_or_create(venue=ampi_tlv, name=section)

        def upsert_artist(name, **extra):
            artist, _ = Artist.objects.update_or_create(
                name=name,
                defaults={
                    'category': 'music',
                    'genre': extra.get('genre') or 'מוזיקה',
                    'description': extra.get('description') or '',
                    'is_international': False,
                    'image': '',
                    'cover_image': '',
                },
            )
            if artist.image or artist.cover_image:
                artist.image = ''
                artist.cover_image = ''
                artist.save(update_fields=['image', 'cover_image'])
            return artist

        next_artist = upsert_artist('NEXT', description='פסטיבל NEXT')
        hysteria = upsert_artist('היסטריה', description='היסטריה — פסטיבל רב-תאריכי')
        ribo = upsert_artist('ישי ריבו')
        banks = upsert_artist(
            'אזיליה בנקס',
            description='קטגוריות כרטיס: עמידה, ישיבה',
        )
        mor = upsert_artist('מור')
        itay = upsert_artist('איתי לוי')
        noam = upsert_artist('נועם בתן')

        specs = [
            {
                'artist': next_artist,
                'name': 'NEXT - אצטדיון רמת גן',
                'date': _il(2026, 10, 22),
                'venue': VENUE_GENERIC,
                'venue_place': ramat_gan,
                'city': 'רמת גן',
                'category': 'festival',
            },
            {
                'artist': next_artist,
                'name': 'NEXT - פיס ארנה ירושלים',
                'date': _il(2026, 12, 7),
                'venue': VENUE_PAIS,
                'venue_place': pais,
                'city': 'ירושלים',
                'category': 'festival',
            },
        ]
        for dt in (
            _il(2026, 12, 3),
            _il(2026, 12, 5),
            _il(2026, 12, 7),
            _il(2026, 12, 8),
            _il(2026, 12, 9),
            _il(2026, 12, 10),
            _il(2026, 12, 12),
            _il(2026, 12, 13),
            _il(2026, 12, 15),
        ):
            specs.append({
                'artist': hysteria,
                'name': 'היסטריה - תל אביב',
                'date': dt,
                'venue': VENUE_MENORA,
                'venue_place': menora,
                'city': 'תל אביב',
                'category': 'festival',
            })
        for dt in (
            _il(2026, 11, 26),
            _il(2026, 11, 28),
            _il(2026, 11, 29),
            _il(2026, 11, 30),
            _il(2026, 12, 1),
        ):
            specs.append({
                'artist': hysteria,
                'name': 'היסטריה - ירושלים',
                'date': dt,
                'venue': VENUE_PAIS,
                'venue_place': pais,
                'city': 'ירושלים',
                'category': 'festival',
            })
        specs.extend([
            {
                'artist': ribo,
                'name': 'ישי ריבו — אמפי MAX',
                'date': _il(2026, 9, 29),
                'venue': VENUE_GENERIC,
                'venue_place': ampi_max,
                'city': 'ראשון לציון',
                'category': 'concert',
            },
            {
                'artist': banks,
                'name': 'אזיליה בנקס — אמפי תל אביב',
                'date': _il(2026, 10, 8),
                'venue': VENUE_GENERIC,
                'venue_place': ampi_tlv,
                'city': 'תל אביב',
                'category': 'concert',
            },
            {
                'artist': mor,
                'name': 'מור — היכל מנורה',
                'date': _il(2026, 11, 12),
                'venue': VENUE_MENORA,
                'venue_place': menora,
                'city': 'תל אביב',
                'category': 'concert',
            },
            {
                'artist': itay,
                'name': 'איתי לוי — היכל מנורה',
                'date': _il(2026, 10, 29),
                'venue': VENUE_MENORA,
                'venue_place': menora,
                'city': 'תל אביב',
                'category': 'concert',
            },
            {
                'artist': noam,
                'name': 'נועם בתן — היכל מנורה',
                'date': _il(2026, 9, 28),
                'venue': VENUE_MENORA,
                'venue_place': menora,
                'city': 'תל אביב',
                'category': 'concert',
            },
        ])

        keep_pks = []
        for spec in specs:
            event, _ = Event.objects.update_or_create(
                artist=spec['artist'],
                date=spec['date'],
                defaults={
                    'name': spec['name'],
                    'venue': spec['venue'],
                    'venue_place': spec['venue_place'],
                    'city': spec['city'],
                    'category': spec['category'],
                    'status': 'פעיל',
                    'country': 'IL',
                    'high_demand': True,
                    'age_restriction': 'ללא הגבלה',
                    'image': '',
                },
            )
            keep_pks.append(event.pk)

        leftover = Event.objects.exclude(pk__in=keep_pks)
        leftover_n = leftover.count()
        if leftover_n:
            self.stdout.write(f'Pruning {leftover_n} events not in the approved catalog')
            leftover.delete()

        Event.objects.filter(pk__in=keep_pks).update(image='')
        Artist.objects.filter(name__in=ALLOWED_ARTISTS).update(image='', cover_image='')
        self.stdout.write(f'Seeded {len(ALLOWED_ARTISTS)} artists and {len(keep_pks)} events (no images)')
