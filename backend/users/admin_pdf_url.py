"""
Staff-only PDF URLs for Django admin: signed Cloudinary raw delivery.

Uses FieldFile.name as the Cloudinary public_id (RawMediaCloudinaryStorage contract).

Delivery: prefer signed api.cloudinary.com download URLs and version-accurate signed CDN URLs.
Plain cloudinary_url(..., type=upload) without the real asset version can yield 401 on res.cloudinary.com.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

from django.conf import settings

_log = logging.getLogger(__name__)


def _public_id_variants(stored_name: str) -> List[str]:
    """MEDIA_URL prefix may or may not match Cloudinary public_id (django-cloudinary-storage)."""
    pid = (stored_name or '').strip().replace('\\', '/')
    if not pid:
        return []
    out = [pid]
    media_prefix = (getattr(settings, 'MEDIA_URL', 'media/') or '').strip().strip('/')
    if media_prefix and pid.startswith(media_prefix + '/'):
        out.append(pid[len(media_prefix) + 1 :])
    elif media_prefix and not pid.startswith(media_prefix):
        out.append(f'{media_prefix}/{pid}')
    seen = set()
    uniq = []
    for x in out:
        if x and x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _raw_extension(public_id: str) -> str:
    ext = os.path.splitext(public_id)[1].lstrip('.').lower()
    return ext or 'pdf'


def get_ticket_pdf_admin_url(ticket) -> Optional[str]:
    """
    URL for admin PDF link / new-tab preview. Local: FieldFile.url.
    Cloudinary: signed URL that returns 200 for the stored raw asset.
    Never raises: failures return None.
    """
    try:
        return _get_ticket_pdf_admin_url_uncaught(ticket)
    except Exception as exc:
        _log.warning(
            'get_ticket_pdf_admin_url failed (ticket pk=%s): %s',
            getattr(ticket, 'pk', None),
            exc,
            exc_info=True,
        )
        return None


def _get_ticket_pdf_admin_url_uncaught(ticket) -> Optional[str]:
    if not ticket:
        return None
    try:
        pdf = getattr(ticket, 'pdf_file', None)
    except Exception:
        return None
    if not pdf:
        return None
    try:
        name = (getattr(pdf, 'name', None) or '').strip()
    except Exception:
        return None
    if not name:
        return None

    if not getattr(settings, 'USE_CLOUDINARY', False):
        try:
            return pdf.url
        except Exception:
            return None

    try:
        import cloudinary.api
        import cloudinary.utils
        from cloudinary.utils import cloudinary_url, private_download_url
    except ImportError:
        try:
            return pdf.url
        except Exception:
            return None

    # 1) Signed API download URL (avoids 401 on raw CDN when version/signature mismatch)
    for pid in _public_id_variants(name):
        ext = _raw_extension(pid)
        try:
            dl = private_download_url(
                pid,
                ext,
                resource_type='raw',
                type='upload',
            )
            if dl and str(dl).startswith('https://'):
                return str(dl)
        except Exception as exc:
            _log.debug('private_download_url failed for %r: %s', pid, exc)

    # 2) Version-aware signed CDN URL (real version from Admin API)
    for pid in _public_id_variants(name):
        info = None
        try:
            info = cloudinary.api.resource(pid, resource_type='raw')
        except Exception:
            continue
        if not info:
            continue
        cid = (info.get('public_id') or pid).replace('\\', '/')
        ver = info.get('version')

        for opts in (
            {
                'resource_type': 'raw',
                'type': 'upload',
                'sign_url': True,
                'secure': True,
                'version': ver,
                'long_url_signature': True,
            },
            {
                'resource_type': 'raw',
                'type': 'upload',
                'sign_url': True,
                'secure': True,
                'version': ver,
                'force_version': bool(ver),
            },
        ):
            try:
                url, _ = cloudinary_url(cid, **opts)
                if url and str(url).startswith('https://'):
                    return str(url)
            except Exception:
                continue

    # 3) Storage delivery URL (unsigned or as configured)
    try:
        u = pdf.url
        if u and str(u).startswith('http'):
            return str(u)
    except Exception:
        pass

    # 4) Last resort: signed URL without version (may 401 on some accounts)
    for pid in _public_id_variants(name):
        try:
            url, _ = cloudinary_url(
                pid,
                resource_type='raw',
                type='upload',
                sign_url=True,
                secure=True,
                force_version=False,
            )
            if url and str(url).startswith('https://'):
                return str(url)
        except Exception:
            continue

    return None
