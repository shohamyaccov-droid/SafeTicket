from django.core.management.base import BaseCommand

from users.artist_seo_copy import apply_artist_bottom_seo_texts


class Command(BaseCommand):
    help = 'Fill Artist.bottom_seo_text for known headliners; skip missing artists with a warning.'

    def handle(self, *args, **options):
        updated, skipped = apply_artist_bottom_seo_texts(stdout=self.stdout)
        for label, count in updated:
            self.stdout.write(self.style.SUCCESS(f'Updated {label} ({count})'))
        if skipped:
            self.stdout.write(self.style.WARNING(f'Skipped missing artists: {", ".join(skipped)}'))
        else:
            self.stdout.write(self.style.SUCCESS('All mapped artists were found.'))
