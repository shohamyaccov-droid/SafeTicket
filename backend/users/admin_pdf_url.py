"""
Staff-only PDF URLs for Django admin: signed Cloudinary raw delivery.

Uses FieldFile.name as the Cloudinary public_id (RawMediaCloudinaryStorage contract).
"""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

_log = logging.getLogger(__name__)


def get_ticket_pdf_admin_url(ticket) -> Optional[str]:
    """
    URL for admin PDF link / new-tab preview. Local: FileField.url.
    Cloudinary: signed raw URL from stored name only (no public_id guessing).
    Never raises: failures (missing file, bad Cloudinary config, NoneType) return None.
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
        from cloudinary.utils import cloudinary_url
    except ImportError:
        try:
            return pdf.url
        except Exception:
            return None

    public_id = name.replace('\\', '/')
    try:
        url, _ = cloudinary_url(
            public_id,
            resource_type='raw',
            type='upload',
            sign_url=True,
            secure=True,
        )
    except Exception:
        try:
            return pdf.url
        except Exception:
            return None
    if url and str(url).startswith('https://'):
        return str(url)
    return None
