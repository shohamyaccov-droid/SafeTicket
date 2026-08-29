"""
Authenticated Cloudinary storage and secure fetch for ticket PDFs and receipts.

Ticket files must never be publicly deliverable via unsigned CDN URLs.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Iterable

from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

CLOUDINARY_AUTHENTICATED_TYPE = 'authenticated'

_ALLOWED_TICKET_EXTS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif'}


def ticket_attachment_magic_bytes_ok(head: bytes) -> bool:
    """True if head looks like a PDF, JPEG, or PNG (ticket upload)."""
    if not head:
        return False
    if head.startswith(b'%PDF'):
        return True
    if head.startswith(b'\xff\xd8\xff'):
        return True
    if len(head) >= 8 and head.startswith(b'\x89PNG\r\n\x1a\n'):
        return True
    return False


def validate_receipt_upload(uploaded_file, *, max_bytes: int = 15 * 1024 * 1024) -> str | None:
    """Return a Hebrew error string if the receipt is not a real PDF/JPEG/PNG."""
    if not uploaded_file:
        return None
    size = getattr(uploaded_file, 'size', None)
    if size is not None and int(size) < 1:
        return 'קובץ הוכחת קנייה ריק.'
    if size is not None and int(size) > max_bytes:
        return 'קובץ הוכחת קנייה גדול מדי (מקס׳ 15MB).'
    name = (getattr(uploaded_file, 'name', '') or '').lower()
    if name and not any(name.endswith(ext) for ext in ('.pdf', '.jpg', '.jpeg', '.png')):
        return 'הוכחת קנייה חייבת להיות PDF, JPG או PNG.'
    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)
        head = uploaded_file.read(12)
        uploaded_file.seek(0)
    else:
        head = b''
    if not ticket_attachment_magic_bytes_ok(head):
        return 'הוכחת קנייה חייבת להיות קובץ PDF, JPG או PNG תקף.'
    return None


def _normalize_ticket_ext(filename: str, *, default: str = '.pdf') -> str:
    ext = os.path.splitext(filename or '')[1].lower()
    if ext in _ALLOWED_TICKET_EXTS:
        return ext
    return default


def ticket_pdf_upload_to(instance, filename: str) -> str:
    """Cryptographically random storage path — never retain the user's original filename."""
    ext = _normalize_ticket_ext(filename, default='.pdf')
    return f'tickets/pdfs/{uuid.uuid4().hex}{ext}'


def ticket_receipt_upload_to(instance, filename: str) -> str:
    ext = _normalize_ticket_ext(filename, default='.pdf')
    return f'tickets/receipts/{uuid.uuid4().hex}{ext}'


def random_ticket_storage_name(ext: str = '.pdf') -> str:
    """Filename for in-memory ContentFile before upload_to runs (extension hint only)."""
    normalized = (ext or '').strip().lower()
    if not normalized.startswith('.'):
        normalized = f'.{normalized}' if normalized else '.pdf'
    if normalized not in _ALLOWED_TICKET_EXTS:
        normalized = '.pdf'
    return f'{uuid.uuid4().hex}{normalized}'


def _public_id_variants(stored_name: str) -> list[str]:
    pid = (stored_name or '').strip().replace('\\', '/')
    if not pid:
        return []
    out = [pid]
    media_prefix = (getattr(settings, 'MEDIA_URL', 'media/') or '').strip().strip('/')
    if media_prefix and pid.startswith(media_prefix + '/'):
        out.append(pid[len(media_prefix) + 1 :])
    elif media_prefix and not pid.startswith(media_prefix):
        out.append(f'{media_prefix}/{pid}')
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        if x and x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _raw_extension(public_id: str) -> str:
    ext = os.path.splitext(public_id)[1].lstrip('.').lower()
    return ext or 'pdf'


class CloudinarySecureFetchError(Exception):
    def __init__(self, message: str, *, errors: list[tuple[str, str]] | None = None):
        super().__init__(message)
        self.errors = errors or []


def fetch_authenticated_cloudinary_bytes(
    stored_name: str,
    *,
    resource_types: Iterable[str] = ('raw', 'image'),
    validate_magic: bool = True,
) -> bytes:
    """
    Load file bytes from Cloudinary using authenticated delivery only (signed URLs / Admin API).

    Never uses unsigned public delivery URLs.
    """
    import requests
    import cloudinary.api
    import cloudinary.utils
    from cloudinary.utils import cloudinary_url, private_download_url

    errors: list[tuple[str, str]] = []

    def _http_get_bytes(url: str) -> bytes | None:
        if not url or not str(url).startswith('http'):
            return None
        r = requests.get(url, timeout=90, headers={'User-Agent': 'TradeTix-SecureFetch/1.0'})
        r.raise_for_status()
        return r.content

    def _validate(body: bytes, label: str) -> bytes:
        body = body.lstrip(b'\xef\xbb\xbf \t\r\n')
        if validate_magic and not ticket_attachment_magic_bytes_ok(body[:12]):
            raise ValueError(f'{label}: response_not_ticket_file')
        return body

    for pid in _public_id_variants(stored_name):
        ext = _raw_extension(pid)
        fmt_candidates = tuple(dict.fromkeys((ext, 'pdf', 'jpg', 'jpeg', 'png')))

        # 1) Signed Admin API download (authenticated type only)
        for fmt in fmt_candidates:
            for resource_type in resource_types:
                try:
                    dl = private_download_url(
                        pid,
                        fmt,
                        resource_type=resource_type,
                        type=CLOUDINARY_AUTHENTICATED_TYPE,
                    )
                    body = _http_get_bytes(dl)
                    if body is not None:
                        return _validate(body, 'private_download_api')
                except Exception as exc:
                    errors.append((f'private_download_{resource_type}_{fmt}', str(exc)[:400]))

        # 2) Version-aware signed CDN URLs (authenticated type only)
        info = None
        resolved_resource_type = None
        for candidate_type in resource_types:
            try:
                info = cloudinary.api.resource(
                    pid,
                    resource_type=candidate_type,
                    type=CLOUDINARY_AUTHENTICATED_TYPE,
                )
                resolved_resource_type = candidate_type
                break
            except Exception as exc:
                errors.append((f'api_resource_{candidate_type}', str(exc)[:400]))

        if not info or not resolved_resource_type:
            continue

        cid = (info.get('public_id') or pid).replace('\\', '/')
        ver = info.get('version')

        url_jobs: list[tuple[str, str]] = []
        seen: set[str] = set()

        for sign in (True,):
            for sig_alg in (None, 'sha1', 'sha256'):
                opts: dict = {
                    'resource_type': resolved_resource_type,
                    'type': CLOUDINARY_AUTHENTICATED_TYPE,
                    'sign_url': sign,
                    'secure': True,
                }
                if ver is not None:
                    opts['version'] = ver
                if sig_alg:
                    opts['signature_algorithm'] = sig_alg
                try:
                    url, _ = cloudinary_url(cid, **opts)
                    if url and url not in seen:
                        seen.add(url)
                        url_jobs.append((f'signed_cdn_{sig_alg or "cfg"}', url))
                except Exception as exc:
                    errors.append(('cloudinary_url', str(exc)[:200]))

            if ver is not None:
                try:
                    url, _ = cloudinary_url(
                        cid,
                        resource_type=resolved_resource_type,
                        type=CLOUDINARY_AUTHENTICATED_TYPE,
                        sign_url=True,
                        secure=True,
                        version=ver,
                        long_url_signature=True,
                    )
                    if url and url not in seen:
                        seen.add(url)
                        url_jobs.append(('signed_cdn_long', url))
                except Exception as exc:
                    errors.append(('cloudinary_url_long', str(exc)[:200]))

        for label, url in url_jobs:
            try:
                body = _http_get_bytes(url)
                if body is not None:
                    return _validate(body, label)
            except Exception as exc:
                errors.append((label, str(exc)[:400]))

    logger.error(
        'fetch_authenticated_cloudinary_bytes failed name=%s strategies=%s',
        stored_name,
        [e[0] for e in errors],
    )
    raise CloudinarySecureFetchError('Could not fetch authenticated Cloudinary asset', errors=errors)


def fetch_ticket_file_field_bytes(file_field, *, validate_magic: bool = True) -> bytes:
    """Fetch bytes for a Ticket pdf_file / receipt_file FieldFile."""
    name = (getattr(file_field, 'name', None) or '').strip()
    if not name:
        raise CloudinarySecureFetchError('empty_file_name')

    if getattr(settings, 'USE_CLOUDINARY', False):
        return fetch_authenticated_cloudinary_bytes(name, validate_magic=validate_magic)

    file_field.open('rb')
    try:
        raw = file_field.read()
    finally:
        file_field.close()
    if validate_magic and raw and not ticket_attachment_magic_bytes_ok(raw[:12]):
        raise CloudinarySecureFetchError('local_file_not_ticket_format')
    return raw
