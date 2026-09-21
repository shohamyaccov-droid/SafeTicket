"""
Do not delete artists/events that have empty images.

Catalog rows are intentionally image-free (copyright). This command is a no-op.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'No-op. Empty artist/event images are expected; records are not deleted.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                'cleanup_empty_images is disabled: catalog rows keep blank image fields on purpose.'
            )
        )
