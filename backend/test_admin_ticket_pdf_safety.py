"""
Admin Ticket PDF: changelist and change view must not 500 on missing/ghost PDFs or URL errors.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from datetime import timedelta

from users.models import Artist, Event, Ticket

User = get_user_model()


def _minimal_pdf_upload(name='ok.pdf'):
    return SimpleUploadedFile(
        name,
        b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n",
        content_type='application/pdf',
    )


@override_settings(ALLOWED_HOSTS=['*'])
class AdminTicketPdfSafetyTests(TestCase):
    """A) changelist 200; B) change view 200; C/D) ghost / forced errors → safe fallback, no crash."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username='admin_pdf_qa',
            email='admin_pdf_qa@test.local',
            password='AdminPdfQA123!',
            is_staff=True,
            is_superuser=True,
        )
        self.seller = User.objects.create_user(
            username='seller_pdf_qa',
            email='seller_pdf_qa@test.local',
            password='SellerPdfQA123!',
            role='seller',
        )
        future = timezone.now() + timedelta(days=30)
        self.artist = Artist.objects.create(name='PDF QA Artist')
        self.event = Event.objects.create(
            name='PDF QA Event',
            artist=self.artist,
            date=future,
            venue='אחר',
            city='תל אביב',
        )
        self.client = Client(HTTP_HOST='localhost')
        self.client.force_login(self.staff)

    def _make_ticket(self):
        return Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            original_price=50,
            pdf_file=_minimal_pdf_upload(),
            delivery_method='instant',
        )

    def test_changelist_200_with_valid_ticket(self):
        self._make_ticket()
        r = self.client.get('/admin/users/ticket/')
        self.assertEqual(r.status_code, 200, r.content[:500])

    def test_change_view_200_with_valid_ticket(self):
        t = self._make_ticket()
        r = self.client.get(f'/admin/users/ticket/{t.pk}/change/')
        self.assertEqual(r.status_code, 200, r.content[:500])

    def test_change_view_shows_new_tab_pdf_cta_when_reachable(self):
        """C) Valid ticket + reachable URL → prominent new-tab link, no iframe (browser PDF embed blocks)."""
        t = self._make_ticket()
        with mock.patch('users.admin.get_ticket_pdf_admin_url', return_value='https://example.com/ticket.pdf'):
            with mock.patch('users.admin.is_admin_delivery_url_reachable', return_value=True):
                r = self.client.get(f'/admin/users/ticket/{t.pk}/change/')
        self.assertEqual(r.status_code, 200, r.content[:500])
        self.assertIn('פתח PDF מאובטח בחלון חדש'.encode('utf-8'), r.content)
        self.assertIn(b'target="_blank"', r.content)
        self.assertNotIn(b'<iframe', r.content.lower())

    def test_changelist_200_ghost_pdf_path(self):
        t = self._make_ticket()
        Ticket.objects.filter(pk=t.pk).update(pdf_file='tickets/pdfs/nonexistent_ghost_file.pdf')
        r = self.client.get('/admin/users/ticket/')
        self.assertEqual(r.status_code, 200, r.content[:500])
        self.assertIn(b'File Error / Missing', r.content)

    def test_change_view_200_ghost_pdf_path(self):
        t = self._make_ticket()
        Ticket.objects.filter(pk=t.pk).update(pdf_file='tickets/pdfs/nonexistent_ghost_file.pdf')
        r = self.client.get(f'/admin/users/ticket/{t.pk}/change/')
        self.assertEqual(r.status_code, 200, r.content[:500])
        self.assertIn(b'File Error / Missing', r.content)

    def test_pdf_staff_link_survives_get_url_exception(self):
        """Forced exception from URL helper must not crash changelist."""
        self._make_ticket()
        path = '/admin/users/ticket/'
        with mock.patch('users.admin.get_ticket_pdf_admin_url', side_effect=RuntimeError('simulated cloudinary failure')):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200, r.content[:500])
        self.assertIn(b'File Error / Missing', r.content)

    def test_pdf_inline_preview_direct_call_never_raises(self):
        from users.admin import TicketAdmin

        t = self._make_ticket()
        Ticket.objects.filter(pk=t.pk).update(pdf_file='tickets/pdfs/ghost.pdf')
        adm = TicketAdmin(Ticket, None)
        html = adm.pdf_inline_preview(t)
        self.assertIsNotNone(html)
        self.assertIn('File Error / Missing', str(html))
