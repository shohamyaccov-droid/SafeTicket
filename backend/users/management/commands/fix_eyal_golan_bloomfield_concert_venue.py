"""
One-off data fix: Eyal Golan shows at Bloomfield use the concert venue label so the
frontend always selects BloomfieldConcertMap (not the football pitch map).

Event model uses `name` (not `title`) for the event title.

Usage:
  python manage.py fix_eyal_golan_bloomfield_concert_venue
"""

from django.core.management.base import BaseCommand

from users.models import Event

VENUE_BLOOMFIELD_CONCERT = 'אצטדיון בלומפילד (הופעות)'


class Command(BaseCommand):
    help = 'Set venue to Bloomfield concert label for events whose name contains אייל גולן.'

    def handle(self, *args, **options):
        from django.db.models import Q

        qs = Event.objects.filter(
            Q(name__icontains='אייל גולן')
            | (Q(category__iexact='concert') & Q(name__icontains='בלומפילד'))
        )
        n = qs.update(venue=VENUE_BLOOMFIELD_CONCERT, category='concert')
        self.stdout.write(self.style.SUCCESS(f'Updated venue/category for {n} event(s).'))
