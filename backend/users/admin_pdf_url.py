"""
Staff-only PDF URLs for Django admin: signed Cloudinary delivery when public URL returns 401.
"""
from __future__ import annotations

import os
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


def get_ticket_pdf_admin_url(ticket) -> Optional[str]:
    """
    Return a URL suitable for admin download / iframe preview.
    - Local storage: FileField.url
    - Cloudinary: prefer signed raw delivery URL; fall back to image resource_type for legacy uploads
    """
    if not ticket or not ticket.pdf_file:
        return None

    try:
        local_url = ticket.pdf_file.url
    except Exception:
        local_url = None

    if not getattr(settings, 'USE_CLOUDINARY', False):
        return local_url

    try:
        import cloudinary.api
        import cloudinary.utils
    except ImportError:
        return local_url

    public_id = (ticket.pdf_file.name or '').replace('\\', '/')
    resource_types_try = ('raw', 'image')

    for pid in _public_id_variants(public_id):
        ext = (os.path.splitext(pid)[1].lstrip('.') or 'pdf').lower()
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
            }
            if ver is not None:
                opts['version'] = ver
            try:
                url, _ = cloudinary.utils.cloudinary_url(cid, **opts)
                return url
            except Exception:
                continue

        for rt in resource_types_try:
            try:
                url, _ = cloudinary.utils.cloudinary_url(
                    pid,
                    resource_type=rt,
                    type='upload',
                    sign_url=True,
                    secure=True,
                )
                return url
            except Exception:
                continue

    return local_url
