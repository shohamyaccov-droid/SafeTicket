from django.db import migrations, models


def backfill_ascii_event_slugs(apps, schema_editor):
    Event = apps.get_model('users', 'Event')
    from users.seo import build_event_slug_base

    used = set()
    for event in Event.objects.select_related('artist').order_by('pk'):
        old = (event.slug or '').strip() or None
        base = (build_event_slug_base(event) or '').strip('-')[:180] or f'event-{event.pk}'
        unique = base
        n = 2
        while unique in used:
            unique = f'{base}-{event.pk}'[:200] if n == 2 else f'{base}-{event.pk}-{n}'[:200]
            n += 1
        used.add(unique)
        legacy = old if old and old != unique else None
        Event.objects.filter(pk=event.pk).update(slug=unique, legacy_slug=legacy)


def restore_legacy_event_slugs(apps, schema_editor):
    Event = apps.get_model('users', 'Event')
    for event in Event.objects.exclude(legacy_slug__isnull=True).exclude(legacy_slug=''):
        Event.objects.filter(pk=event.pk).update(slug=event.legacy_slug)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0084_artist_bottom_seo_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='legacy_slug',
            field=models.SlugField(
                allow_unicode=True,
                blank=True,
                db_index=True,
                help_text='Previous Hebrew/unicode slug kept so old /event/… links still resolve.',
                max_length=220,
                null=True,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name='event',
            name='slug',
            field=models.SlugField(
                allow_unicode=True,
                blank=True,
                db_index=True,
                help_text='ASCII URL slug: artist English slug + event date (e.g. itay-levi-2026-08-29).',
                max_length=220,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(backfill_ascii_event_slugs, restore_legacy_event_slugs),
    ]
