"""
One-time / maintenance: drop non-essential artists and recreate them from local image files (Cloudinary upload).

⚠️  DESTRUCTIVE: Deleting an Artist CASCADE-deletes all related Events (and their Tickets, etc.).

Kept artists (never deleted):
  Odeya / עודיה, Omer Adam / עומר אדם, Eyal Golan / אייל גולן  (+ common spelling variants)

Local images (default directory):
  <repo>/frontend/src/assets/artists/

File naming (see --map for overrides):
  • cover_<slug>.<ext>  -> cover_image (slug: lowercase, underscores for spaces, ASCII ok)
  • profile_<slug>.<ext> or img_<slug>.<ext> -> image (profile photo)
  • <slug>.<ext> with no prefix -> cover_image

  Use --map to map slug -> exact display name (e.g. Hebrew). Without --map, slug is turned into
  Title Case words from underscores (fallback only).

USAGE — local (from repo, NEVER run on production without backup):

  cd backend
  # Optional: place files in frontend/src/assets/artists/ first
  python manage.py sync_artists --dry-run
  python manage.py sync_artists

With custom folder + JSON map:

  python manage.py sync_artists --images-dir "C:/Users/shoham/Pictures/artists" --map "C:/path/artist_map.json"

artist_map.json example:
  {
    "noa_kirel": "נועה קירל",
    "shlomo_artzi": "שלמה ארצי"
  }

Render / production:
  1. Take a DATABASE backup and download it if needed.
  2. Prefer running against a STAGING dump locally first.
  3. On Render Shell (or one-off job), with CLOUDINARY_* env vars set:
       python manage.py sync_artists --images-dir /opt/render/project/src/frontend/src/assets/artists
     (adjust path to where you uploaded images in the service filesystem — often you must scp
      images into the instance or use a release-phase script; Render ephemeral disk may not
      persist Shoham’s local folder — **usually run locally against a copy of prod DB**, then
      migrate data, or run once from CI with artifacts attached.)

"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import Artist

# Artists that must never be deleted (any match wins).
_KEEP_NAME_GROUPS = (
    frozenset({'odeya', 'עודיה', 'odiya', 'אודיה'}),
    frozenset({'omer adam', 'עומר אדם', 'omer-adam', 'omradam', 'עומראדם'}),
    frozenset({'eyal golan', 'אייל גולן', 'eyal-golan', 'eyalgolan', 'איילגולן'}),
)

_IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}


def _norm_key(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip().lower())


def _artist_matches_keep(name: str) -> bool:
    key = _norm_key(name)
    key_compact = re.sub(r'[\s_.-]+', '', key)
    for group in _KEEP_NAME_GROUPS:
        for g in group:
            gk = _norm_key(g)
            gc = re.sub(r'[\s_.-]+', '', gk)
            if key == gk or key_compact == gc:
                return True
            if gk and (gk in key or key in gk):
                return True
            if gc and (gc in key_compact or key_compact in gc):
                return True
    return False


def _slug_to_default_name(slug: str) -> str:
    parts = slug.replace('-', '_').split('_')
    return ' '.join(p.capitalize() for p in parts if p)


def _parse_filename(filename: str) -> tuple[str, str] | None:
    """
    Return (field_name, slug) where field_name is 'cover_image' | 'image'.
    """
    stem, ext = os.path.splitext(filename)
    if ext.lower() not in _IMAGE_SUFFIXES:
        return None
    lower = stem.lower()
    if lower.startswith('cover_'):
        return 'cover_image', stem[6:].strip('_').lower()
    if lower.startswith('profile_') or lower.startswith('img_'):
        prefix = 'profile_' if lower.startswith('profile_') else 'img_'
        return 'image', stem[len(prefix) :].strip('_').lower()
    return 'cover_image', lower


class Command(BaseCommand):
    help = (
        'Delete artists except Odeya / Omer Adam / Eyal Golan, then create artists from local images '
        '(uploads via default storage -> Cloudinary when configured).'
    )

    def add_arguments(self, parser):
        root = Path(settings.BASE_DIR).resolve().parent
        default_dir = root / 'frontend' / 'src' / 'assets' / 'artists'
        parser.add_argument(
            '--images-dir',
            type=str,
            default=str(default_dir),
            help=f'Directory of image files (default: {default_dir})',
        )
        parser.add_argument(
            '--map',
            type=str,
            default='',
            help='Optional JSON file: object mapping slug -> exact artist display name',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print actions only; do not delete or write',
        )
        parser.add_argument(
            '--update-kept',
            action='store_true',
            help='Also assign images from files whose mapped name matches a kept artist',
        )

    def handle(self, *args, **opts):
        images_dir = Path(opts['images_dir']).expanduser().resolve()
        dry = opts['dry_run']
        map_path = (opts['map'] or '').strip()
        update_kept = opts['update_kept']

        if not images_dir.is_dir():
            raise CommandError(
                f'Images directory does not exist: {images_dir}\n'
                f'Create it and add files, e.g. mkdir -p frontend/src/assets/artists'
            )

        if not getattr(settings, 'USE_CLOUDINARY', False):
            self.stdout.write(
                self.style.WARNING(
                    'USE_CLOUDINARY is False — files will use local MEDIA storage. '
                    'For Cloudinary uploads set USE_CLOUDINARY=True and CLOUDINARY_* in the environment.'
                )
            )

        slug_to_name: dict[str, str] = {}
        if map_path:
            mp = Path(map_path).expanduser().resolve()
            if not mp.is_file():
                raise CommandError(f'--map file not found: {mp}')
            with open(mp, encoding='utf-8') as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                raise CommandError('--map JSON must be an object { "slug": "Display Name", ... }')
            slug_to_name = {k.strip().lower(): str(v).strip() for k, v in raw.items() if k and v}

        keep_qs = [a for a in Artist.objects.all() if _artist_matches_keep(a.name)]
        keep_ids = {a.pk for a in keep_qs}
        self.stdout.write(self.style.NOTICE(f'Keeping {len(keep_ids)} artist(s): {[a.name for a in keep_qs]}'))

        to_delete = Artist.objects.exclude(pk__in=keep_ids)
        del_count = to_delete.count()
        from users.models import Event

        ev_count = Event.objects.filter(artist_id__in=to_delete.values_list('pk', flat=True)).count()
        self.stdout.write(
            self.style.WARNING(
                f'Will DELETE {del_count} artist(s) and CASCADE ~{ev_count} event(s) linked to them.'
            )
        )

        if dry:
            self.stdout.write(self.style.NOTICE('DRY-RUN: no database changes.'))
        else:
            with transaction.atomic():
                to_delete.delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {del_count} artist(s).'))

        # Collect file specs: field, slug, path
        file_specs: list[tuple[str, str, Path]] = []
        for p in sorted(images_dir.iterdir()):
            if not p.is_file():
                continue
            parsed = _parse_filename(p.name)
            if not parsed:
                continue
            field, slug = parsed
            file_specs.append((field, slug, p))

        if not file_specs:
            self.stdout.write(self.style.WARNING(f'No image files found under {images_dir}'))
        else:
            self.stdout.write(f'Found {len(file_specs)} image file(s).')

        # slug -> { 'cover_image': Path | None, 'image': Path | None }
        by_slug: dict[str, dict[str, Path | None]] = {}
        for field, slug, path in file_specs:
            if slug not in by_slug:
                by_slug[slug] = {'cover_image': None, 'image': None}
            by_slug[slug][field] = path

        for slug, paths in sorted(by_slug.items()):
            display_name = slug_to_name.get(slug) or _slug_to_default_name(slug)
            is_kept_name = _artist_matches_keep(display_name)
            if is_kept_name and not update_kept:
                self.stdout.write(f'  Skip file group slug={slug!r} (matches kept artist; use --update-kept)')
                continue

            if dry:
                self.stdout.write(f'  Would upsert {display_name!r} from {paths}')
                continue

            artist, _created = Artist.objects.get_or_create(
                name=display_name,
                defaults={'description': '', 'genre': ''},
            )
            if is_kept_name and update_kept:
                self.stdout.write(self.style.NOTICE(f'Updating kept artist: {artist.name}'))

            for field_name in ('cover_image', 'image'):
                path = paths.get(field_name)
                if path is None:
                    continue
                with open(path, 'rb') as fh:
                    django_file = File(fh, name=path.name)
                    getattr(artist, field_name).save(path.name, django_file, save=True)
            self.stdout.write(self.style.SUCCESS(f'  OK {artist.name} (pk={artist.pk})'))

        # Validation
        self.stdout.write('')
        self.stdout.write(self.style.NOTICE('Validation: artists without image or cover_image'))
        bad = []
        for a in Artist.objects.all().order_by('name'):
            has_cover = bool(getattr(a.cover_image, 'name', None))
            has_profile = bool(getattr(a.image, 'name', None))
            if not has_cover and not has_profile:
                bad.append(a)
                self.stdout.write(self.style.ERROR(f'  MISSING both fields: {a.pk} {a.name!r}'))
            elif not has_cover:
                self.stdout.write(self.style.WARNING(f'  No cover (profile only): {a.name!r}'))
            elif not has_profile:
                self.stdout.write(self.style.WARNING(f'  No profile (cover only): {a.name!r}'))

        if bad:
            msg = f'{len(bad)} artist(s) have no cover_image and no image.'
            if dry:
                self.stdout.write(self.style.WARNING(msg))
            else:
                raise CommandError(msg)
        else:
            self.stdout.write(self.style.SUCCESS('All artists have at least one of cover_image / image.'))
