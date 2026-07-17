# Generated manually for Event.slug + backfill
#
# Production already has users_event.slug (+ unique / pattern_ops indexes) while
# migration history lagged. Fresh DBs (tests, new envs) still need the column.
# Schema steps are therefore conditional: create only if missing.

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


def _event_column_names(schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        return {
            col.name
            for col in connection.introspection.get_table_description(cursor, 'users_event')
        }


def ensure_slug_column(apps, schema_editor):
    """Add slug column + indexes only when the physical column is missing."""
    if 'slug' in _event_column_names(schema_editor):
        return

    Event = apps.get_model('users', 'Event')
    field = models.SlugField(
        allow_unicode=True,
        blank=True,
        db_index=True,
        help_text='URL-friendly unique slug for programmatic SEO (auto-generated).',
        max_length=220,
        null=True,
        unique=False,
    )
    field.set_attributes_from_name('slug')
    schema_editor.add_field(Event, field)


def ensure_slug_unique(apps, schema_editor):
    """Promote slug to unique only when the column exists and is not yet unique."""
    if 'slug' not in _event_column_names(schema_editor):
        return

    Event = apps.get_model('users', 'Event')
    connection = schema_editor.connection
    # If a unique constraint / unique index already exists, AlterField would fail
    # on production — detect via constraints + indexes.
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, 'users_event')
    for meta in constraints.values():
        cols = meta.get('columns') or []
        if cols == ['slug'] and (meta.get('unique') or meta.get('primary_key')):
            return

    old_field = models.SlugField(
        allow_unicode=True,
        blank=True,
        db_index=True,
        help_text='URL-friendly unique slug for programmatic SEO (auto-generated).',
        max_length=220,
        null=True,
        unique=False,
    )
    old_field.set_attributes_from_name('slug')
    new_field = models.SlugField(
        allow_unicode=True,
        blank=True,
        db_index=True,
        help_text='URL-friendly unique slug for programmatic SEO (auto-generated).',
        max_length=220,
        null=True,
        unique=True,
    )
    new_field.set_attributes_from_name('slug')
    schema_editor.alter_field(Event, old_field, new_field)


def backfill_slugs(apps, schema_editor):
    if 'slug' not in _event_column_names(schema_editor):
        return

    Event = apps.get_model('users', 'Event')
    used = set(
        Event.objects.exclude(slug__isnull=True).exclude(slug='').values_list('slug', flat=True)
    )
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
        # Register slug on Django state; physical DDL is conditional (see ensure_*).
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
            database_operations=[
                migrations.RunPython(ensure_slug_column, noop_reverse),
            ],
        ),
        migrations.RunPython(backfill_slugs, noop_reverse),
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
            database_operations=[
                migrations.RunPython(ensure_slug_unique, noop_reverse),
            ],
        ),
    ]
