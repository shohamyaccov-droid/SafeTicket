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


def is_admin_delivery_url_reachable(url: str, timeout: int = 25) -> bool:
    """
    True if the URL returns OK bytes (HEAD or GET). Used so admin can show a message
    instead of embedding when the asset is missing (404/401) or legacy disk path.
    Never raises (network, SSL, invalid URL, etc.).
    """
    try:
        if not url or not (str(url).startswith('http://') or str(url).startswith('https://')):
            return False
        try:
            import requests
        except ImportError:
            return True

        # Some CDNs (incl. Cloudinary signed raw) return 403 to non-browser HEAD; use a real Chrome UA.
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            ),
        }
        try:
            r = requests.head(url, timeout=timeout, allow_redirects=True, headers=headers)
            if r.status_code == 200:
                return True
            if r.status_code in (401, 403, 404):
                return False
            if r.status_code == 405:
                r2 = requests.get(
                    url,
                    timeout=timeout,
                    allow_redirects=True,
                    headers=headers,
                    stream=True,
                )
                return r2.status_code == 200
            return False
        except Exception:
            try:
                r = requests.get(
                    url,
                    timeout=timeout,
                    allow_redirects=True,
                    headers=headers,
                    stream=True,
                )
                ok = r.status_code == 200
                r.close()
                return ok
            except Exception:
                return False
    except Exception as exc:
        _log.warning('is_admin_delivery_url_reachable failed for url=%r: %s', url, exc, exc_info=True)
        return False
