"""
Cloudinary storage backends for ticket PDFs and receipts (type=authenticated only).

Loaded via STORAGES when USE_CLOUDINARY=True — not imported from models at startup.
"""
from __future__ import annotations

import os

from cloudinary_storage.storage import MediaCloudinaryStorage, RawMediaCloudinaryStorage
from django.core.files.base import ContentFile
from django.utils.deconstruct import deconstructible

from users.secure_ticket_storage import CLOUDINARY_AUTHENTICATED_TYPE, fetch_authenticated_cloudinary_bytes


@deconstructible
class AuthenticatedRawMediaCloudinaryStorage(RawMediaCloudinaryStorage):
    """Raw ticket/receipt uploads with type=authenticated (not publicly deliverable)."""

    def _upload(self, name, content):
        import cloudinary.uploader

        options = {
            'use_filename': True,
            'resource_type': self._get_resource_type(name),
            'tags': self.TAG,
            'type': CLOUDINARY_AUTHENTICATED_TYPE,
        }
        folder = os.path.dirname(name)
        if folder:
            options['folder'] = folder
        return cloudinary.uploader.upload(content, **options)

    def _get_url(self, name):
        import cloudinary

        name = self._prepend_prefix(name)
        return cloudinary.CloudinaryResource(
            name,
            default_resource_type=self._get_resource_type(name),
            type=CLOUDINARY_AUTHENTICATED_TYPE,
        ).url

    def exists(self, name):
        import cloudinary.api

        try:
            cloudinary.api.resource(
                self._prepend_prefix(name),
                resource_type=self._get_resource_type(name),
                type=CLOUDINARY_AUTHENTICATED_TYPE,
            )
            return True
        except Exception:
            return False

    def _open(self, name, mode='rb'):
        content = fetch_authenticated_cloudinary_bytes(
            self._prepend_prefix(name),
            validate_magic=False,
        )
        file = ContentFile(content)
        file.name = name
        file.mode = mode
        return file


@deconstructible
class AuthenticatedMediaCloudinaryStorage(MediaCloudinaryStorage):
    """Image uploads with type=authenticated (reserved for future use)."""

    def _upload(self, name, content):
        import cloudinary.uploader

        options = {
            'use_filename': True,
            'resource_type': self._get_resource_type(name),
            'tags': self.TAG,
            'type': CLOUDINARY_AUTHENTICATED_TYPE,
        }
        folder = os.path.dirname(name)
        if folder:
            options['folder'] = folder
        return cloudinary.uploader.upload(content, **options)

    def _get_url(self, name):
        import cloudinary

        name = self._prepend_prefix(name)
        return cloudinary.CloudinaryResource(
            name,
            default_resource_type=self._get_resource_type(name),
            type=CLOUDINARY_AUTHENTICATED_TYPE,
        ).url

    def exists(self, name):
        import cloudinary.api

        try:
            cloudinary.api.resource(
                self._prepend_prefix(name),
                resource_type=self._get_resource_type(name),
                type=CLOUDINARY_AUTHENTICATED_TYPE,
            )
            return True
        except Exception:
            return False

    def _open(self, name, mode='rb'):
        content = fetch_authenticated_cloudinary_bytes(
            self._prepend_prefix(name),
            resource_types=('image', 'raw'),
            validate_magic=False,
        )
        file = ContentFile(content)
        file.name = name
        file.mode = mode
        return file
