from django.db import migrations, models


def backfill_artist_slugs(apps, schema_editor):
    Artist = apps.get_model('users', 'Artist')
    from users.seo import build_artist_slug_base, ensure_unique_artist_slug

    for artist in Artist.objects.order_by('pk'):
        if artist.slug:
            continue
        slug = ensure_unique_artist_slug(artist, build_artist_slug_base(artist))
        Artist.objects.filter(pk=artist.pk).update(slug=slug)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0082_paymewebhooklog'),
    ]

    operations = [
        migrations.AddField(
            model_name='artist',
            name='slug',
            field=models.SlugField(
                allow_unicode=True,
                blank=True,
                db_index=True,
                help_text='URL-friendly unique slug for artist SEO pages (auto-generated).',
                max_length=220,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(backfill_artist_slugs, noop_reverse),
    ]
