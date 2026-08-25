from django.db import migrations, models


def apply_bottom_seo_copy(apps, schema_editor):
    Artist = apps.get_model('users', 'Artist')
    from users.artist_seo_copy import apply_artist_bottom_seo_texts

    apply_artist_bottom_seo_texts(artist_model=Artist)


def clear_bottom_seo_copy(apps, schema_editor):
    Artist = apps.get_model('users', 'Artist')
    from users.artist_seo_copy import ARTIST_BOTTOM_SEO_TEXTS

    names = [name for row in ARTIST_BOTTOM_SEO_TEXTS for name in row['names']]
    slugs = [slug for row in ARTIST_BOTTOM_SEO_TEXTS for slug in row['slugs']]
    Artist.objects.filter(models.Q(name__in=names) | models.Q(slug__in=slugs)).update(
        bottom_seo_text=None
    )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0083_artist_seo_slug'),
    ]

    operations = [
        migrations.AddField(
            model_name='artist',
            name='bottom_seo_text',
            field=models.TextField(
                blank=True,
                help_text='Long-form SEO copy rendered at the bottom of the public artist hub page.',
                null=True,
            ),
        ),
        migrations.RunPython(apply_bottom_seo_copy, clear_bottom_seo_copy),
    ]
