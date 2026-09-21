"""Client catalog seed: exact 7 artists, no images, no extra names."""
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings

from users.models import Artist, Event


TINY_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
    b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


@override_settings(DEBUG=True, SECRET_KEY='client-catalog-secret')
class SeedClientCatalogTests(TestCase):
    def test_wipe_seeds_exact_artists_without_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with self.settings(MEDIA_ROOT=media):
                junk = Artist.objects.create(name='אסף אמדורסקי')
                junk.image.save('junk.png', SimpleUploadedFile('junk.png', TINY_PNG, content_type='image/png'))
                Event.objects.create(
                    artist=junk,
                    name='Junk Show',
                    date='2026-08-01T20:00:00+03:00',
                    venue='היכל מנורה מבטחים',
                    city='תל אביב',
                    status='פעיל',
                )

                call_command('seed_client_catalog', wipe=True)

                names = set(Artist.objects.values_list('name', flat=True))
                self.assertEqual(
                    names,
                    {'NEXT', 'אזיליה בנקס', 'איתי לוי', 'היסטריה', 'ישי ריבו', 'מור', 'נועם בתן'},
                )
                self.assertEqual(Artist.objects.count(), 7)
                self.assertEqual(Event.objects.count(), 35)
                self.assertFalse(Artist.objects.exclude(image='').exclude(image__isnull=True).exists())
                self.assertFalse(Artist.objects.exclude(cover_image='').exclude(cover_image__isnull=True).exists())
                self.assertFalse(Event.objects.exclude(image='').exclude(image__isnull=True).exists())
                self.assertEqual(Event.objects.filter(name='NEXT - אצטדיון רמת גן').count(), 10)
                self.assertEqual(Event.objects.filter(name='NEXT - פיס ארנה ירושלים').count(), 6)
                self.assertEqual(Event.objects.filter(name='היסטריה - תל אביב').count(), 9)
                self.assertEqual(Event.objects.filter(name='היסטריה - ירושלים').count(), 5)
                self.assertTrue(all(ev.status == 'פעיל' for ev in Event.objects.all()))
                self.assertTrue(all(ev.high_demand for ev in Event.objects.all()))
                self.assertTrue(all(not a.is_international for a in Artist.objects.all()))
                self.assertFalse(Artist.objects.filter(name='אסף אמדורסקי').exists())
