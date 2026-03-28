"""
Staff-only PDF URLs for Django admin: signed Cloudinary delivery when public/raw URLs return 401.
"""
from __future__ import annotations

from typing import Optional

from django.conf import settings


def _public_id_variants(public_id: str) -> list[str]:
    pid = (public_id or '').strip().strip('/').replace('\\', '/')
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
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _all_public_id_candidates(stored_name: str) -> list[str]:
    """Try with/without .pdf — django-cloudinary-storage and folder prefixes vary."""
    base = stored_name.replace('\\', '/').strip()
    if not base:
        return []
    seen = set()
    ordered: list[str] = []

    def add(p: str):
        p = p.strip().strip('/')
        if not p or p in seen:
            return
        seen.add(p)
        ordered.append(p)

    for v in _public_id_variants(base):
        add(v)
        low = v.lower()
        if low.endswith('.pdf'):
            add(v[:-4])
        else:
            add(v + '.pdf')
    return ordered


def _try_cloudinary_signed_raw_urls(public_id: str) -> list[str]:
    from cloudinary.utils import cloudinary_url

    urls: list[str] = []
    for pid in _all_public_id_candidates(public_id):
        option_sets = (
            {
                'resource_type': 'raw',
                'type': 'upload',
                'sign_url': True,
                'secure': True,
                'long_url_signature': True,
            },
            {
                'resource_type': 'raw',
                'type': 'upload',
                'sign_url': True,
                'secure': True,
            },
        )
        for opts in option_sets:
            try:
                url, _ = cloudinary_url(pid, **opts)
                if url and str(url).startswith('https://') and url not in urls:
                    urls.append(str(url))
            except Exception:
                continue
    return urls


def get_ticket_pdf_admin_url(ticket) -> Optional[str]:
    """
    Return a URL suitable for admin download / iframe preview.
    - Local storage: FileField.url
    - Cloudinary: prefer signed raw delivery URL; fall back to api.resource + version; legacy image type
    """
    try:
        return _get_ticket_pdf_admin_url_uncaught(ticket)
    except Exception:
        return None


def _get_ticket_pdf_admin_url_uncaught(ticket) -> Optional[str]:
    if not ticket:
        return None
    pdf = getattr(ticket, 'pdf_file', None)
    if not pdf:
        return None
    name = (getattr(pdf, 'name', None) or '').strip()
    if not name:
        return None

    try:
        local_url = pdf.url
    except (ValueError, AttributeError):
        local_url = None
    except Exception:
        local_url = None

    if not getattr(settings, 'USE_CLOUDINARY', False):
        return local_url

    try:
        import cloudinary.api
        from cloudinary.utils import cloudinary_url
    except ImportError:
        return local_url

    public_id = name.replace('\\', '/')
    resource_types_try = ('raw', 'image')

    # 1) Signed delivery URLs (raw) — longest signature first
    for url in _try_cloudinary_signed_raw_urls(public_id):
        return url

    # 2) Resolve exact public_id + version from Admin API, then sign
    try:
        for pid in _all_public_id_candidates(public_id):
            for rt in resource_types_try:
                try:
                    info = cloudinary.api.resource(pid, resource_type=rt)
                except Exception:
                    info = None
                if not info:
                    continue
                cid = info.get('public_id') or pid
                ver = info.get('version')
                opts = {
                    'resource_type': rt,
                    'type': 'upload',
                    'sign_url': True,
                    'secure': True,
                    'long_url_signature': True,
                }
                if ver is not None:
                    opts['version'] = ver
                try:
                    url, _ = cloudinary_url(cid, **opts)
                    if url:
                        return url
                except Exception:
                    continue

            for rt in resource_types_try:
                try:
                    url, _ = cloudinary_url(
                        pid,
                        resource_type=rt,
                        type='upload',
                        sign_url=True,
                        secure=True,
                        long_url_signature=True,
                    )
                    if url:
                        return url
                except Exception:
                    continue
    except Exception:
        return local_url

    return local_url
