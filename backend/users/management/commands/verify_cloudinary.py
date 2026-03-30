"""
Temporary verification: upload a tiny file via STORAGES['ticket_pdfs'], build a signed raw URL,
GET it, assert HTTP 200.

Usage (repo root .env with CLOUDINARY_URL=... and USE_CLOUDINARY=True):
  cd backend && python manage.py verify_cloudinary
"""

from __future__ import annotations

import uuid

import requests
from cloudinary.utils import cloudinary_url
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Verify Cloudinary raw storage + signed URL returns 200'

    def handle(self, *args, **options):
        if not getattr(settings, 'USE_CLOUDINARY', False):
            raise CommandError(
                'USE_CLOUDINARY is false. Set CLOUDINARY_URL (or split CLOUDINARY_* vars) in the environment.'
            )

        raw = storages['ticket_pdfs']
        key = f'safeticket_verify_{uuid.uuid4().hex}.txt'
        saved_name = raw.save(key, ContentFile(b'cloudinary verify ok\n'))
        public_id = (saved_name or key).replace('\\', '/')

        url, _opts = cloudinary_url(
            public_id,
            resource_type='raw',
            type='upload',
            sign_url=True,
            secure=True,
        )
        if not url or not str(url).startswith('https://'):
            raise CommandError('cloudinary_url did not return an https URL')

        r = requests.get(
            url,
            timeout=90,
            headers={'User-Agent': 'TradeTix-verify-cloudinary/1.0'},
        )
        if r.status_code != 200:
            raise CommandError(f'Expected HTTP 200 from signed URL, got {r.status_code}')

        self.stdout.write(self.style.SUCCESS(f'verify_cloudinary OK: status=200 public_id={public_id}'))
