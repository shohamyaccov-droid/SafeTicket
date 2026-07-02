"""Tests for secure ticket storage paths and authenticated fetch behavior."""
from __future__ import annotations

import os
import re
import uuid
from unittest import mock

from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings

from users.secure_ticket_storage import (
    CloudinarySecureFetchError,
    fetch_authenticated_cloudinary_bytes,
    random_ticket_storage_name,
    ticket_pdf_upload_to,
    ticket_receipt_upload_to,
)


class TicketUploadPathTests(SimpleTestCase):
    def test_pdf_upload_path_is_random_uuid(self):
        path = ticket_pdf_upload_to(mock.Mock(), 'my-secret-ticket.pdf')
        self.assertTrue(path.startswith('tickets/pdfs/'))
        self.assertNotIn('my-secret', path)
        self.assertNotIn('secret-ticket', path)
        hex_part = os.path.splitext(os.path.basename(path))[0]
        uuid.UUID(hex_part)

    def test_receipt_upload_path_is_random_uuid(self):
        path = ticket_receipt_upload_to(mock.Mock(), 'receipt-scan.jpg')
        self.assertTrue(path.startswith('tickets/receipts/'))
        self.assertNotIn('receipt-scan', path)
        self.assertTrue(path.endswith('.jpg'))

    def test_random_storage_name_uses_uuid(self):
        name = random_ticket_storage_name('.png')
        self.assertTrue(name.endswith('.png'))
        uuid.UUID(os.path.splitext(name)[0])


class AuthenticatedFetchTests(SimpleTestCase):
    @override_settings(USE_CLOUDINARY=True)
    @mock.patch('requests.get')
    @mock.patch('cloudinary.api.resource')
    @mock.patch('cloudinary.utils.private_download_url')
    def test_fetch_uses_authenticated_private_download_only(self, mock_private_dl, mock_resource, mock_get):
        mock_private_dl.return_value = 'https://api.cloudinary.com/v1_1/x/raw/download?type=authenticated'
        mock_get.return_value = mock.Mock(
            status_code=200,
            content=b'%PDF-1.4\n',
            raise_for_status=mock.Mock(),
        )

        body = fetch_authenticated_cloudinary_bytes('tickets/pdfs/abc123.pdf')

        self.assertTrue(body.startswith(b'%PDF'))
        mock_private_dl.assert_called()
        call_kwargs = mock_private_dl.call_args.kwargs
        self.assertEqual(call_kwargs.get('type'), 'authenticated')
        mock_resource.assert_not_called()
        mock_get.assert_called_once()

    @override_settings(USE_CLOUDINARY=True)
    @mock.patch('requests.get')
    @mock.patch('cloudinary.utils.cloudinary_url')
    @mock.patch('cloudinary.api.resource')
    @mock.patch('cloudinary.utils.private_download_url', side_effect=Exception('no private'))
    def test_fetch_does_not_use_unsigned_public_url(self, _mock_private, mock_resource, mock_cloud_url, mock_get):
        mock_resource.return_value = {
            'public_id': 'tickets/pdfs/abc123.pdf',
            'version': 1,
        }
        mock_cloud_url.return_value = ('https://res.cloudinary.com/x/raw/authenticated/s--sig--/v1/tickets/pdfs/abc123.pdf', {})
        mock_get.return_value = mock.Mock(
            status_code=200,
            content=b'%PDF-1.4\n',
            raise_for_status=mock.Mock(),
        )

        body = fetch_authenticated_cloudinary_bytes('tickets/pdfs/abc123.pdf')
        self.assertTrue(body.startswith(b'%PDF'))

        for call in mock_cloud_url.call_args_list:
            self.assertEqual(call.kwargs.get('type'), 'authenticated')
            self.assertTrue(call.kwargs.get('sign_url'))

    @override_settings(USE_CLOUDINARY=True)
    @mock.patch('cloudinary.utils.private_download_url', side_effect=Exception('fail'))
    @mock.patch('cloudinary.api.resource', side_effect=Exception('not found'))
    def test_fetch_raises_when_authenticated_asset_missing(self, *_mocks):
        with self.assertRaises(CloudinarySecureFetchError):
            fetch_authenticated_cloudinary_bytes('tickets/pdfs/missing.pdf')
