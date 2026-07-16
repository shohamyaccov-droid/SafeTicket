# Generated manually for Event.slug + backfill

from django.db import migrations, models
from django.utils import timezone
from django.utils.text import slugify


def _slug_base(event):
    artist_name = ''
    if event.artist_id:
        try:
            artist_name = (event.artist.name or '').strip()
        except Exception:
            artist_name = ''
    city = (event.city or '').strip()
    name = (event.name or '').strip()
    if artist_name and city:
        raw = f'{artist_name}-{city}'
    elif artist_name:
        raw = artist_name
    else:
        raw = name or city or 'event'
    base = slugify(raw, allow_unicode=True) or f'event-{event.pk}'
    if event.date:
        try:
            dt = event.date
            if timezone.is_aware(dt):
                dt = timezone.localtime(dt)
            base = slugify(f'{base}-{dt.strftime("%Y-%m-%d")}', allow_unicode=True) or base
        except Exception:
            pass
    return (base or f'event-{event.pk}')[:180]


def backfill_slugs(apps, schema_editor):
    Event = apps.get_model('users', 'Event')
    used = set(Event.objects.exclude(slug__isnull=True).exclude(slug='').values_list('slug', flat=True))
    for event in Event.objects.select_related('artist').order_by('pk'):
        if event.slug:
            used.add(event.slug)
            continue
        candidate = _slug_base(event)
        unique = candidate
        n = 2
        while unique in used:
            unique = f'{candidate}-{event.pk}' if n == 2 else f'{candidate}-{event.pk}-{n}'
            unique = unique[:200]
            n += 1
        Event.objects.filter(pk=event.pk).update(slug=unique)
        used.add(unique)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0068_global_fee_settings'),
    ]

    operations = [
        # The slug column and its indexes (incl. the varchar_pattern_ops
        # "users_event_slug_697e89ba_like" index created by db_index=True) already
        # exist on production — the DB schema is out of sync with migration history.
        # Register the field in Django's state ONLY; emit no DDL so the deploy stops
        # crashing with DuplicateTable on the "_like" relation.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='event',
                    name='slug',
                    field=models.SlugField(
                        allow_unicode=True,
                        blank=True,
                        db_index=True,
                        help_text='URL-friendly unique slug for programmatic SEO (auto-generated).',
                        max_length=220,
                        null=True,
                        unique=False,
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(backfill_slugs, noop_reverse),
        # Promote to unique in state only; the unique index already exists in the DB.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='event',
                    name='slug',
                    field=models.SlugField(
                        allow_unicode=True,
                        blank=True,
                        db_index=True,
                        help_text='URL-friendly unique slug for programmatic SEO (auto-generated).',
                        max_length=220,
                        null=True,
                        unique=True,
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
