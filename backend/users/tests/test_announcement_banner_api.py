from django.test import TestCase
from rest_framework.test import APIClient

from users.models import AnnouncementBanner


class AnnouncementBannerApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/users/site/announcement-banner/'

    def test_banner_defaults_to_inactive_when_not_configured(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json(), {'banner_text': '', 'is_active': False})

    def test_banner_returns_active_text_when_enabled(self):
        banner = AnnouncementBanner.load()
        banner.banner_text = 'מבצע בדיקה'
        banner.is_active = True
        banner.save(update_fields=['banner_text', 'is_active', 'updated_at'])

        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json(), {'banner_text': 'מבצע בדיקה', 'is_active': True})

    def test_banner_hides_when_active_without_text(self):
        banner = AnnouncementBanner.load()
        banner.banner_text = '   '
        banner.is_active = True
        banner.save(update_fields=['banner_text', 'is_active', 'updated_at'])

        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json(), {'banner_text': '', 'is_active': False})
