from django.db import migrations, models


def backfill_artist_market_fields(apps, schema_editor):
    Artist = apps.get_model('users', 'Artist')

    standup_terms = ['סטנדאפ', 'קומיק', 'Comedy', 'comedy']
    sports_terms = [
        'כדורגל',
        'ספורט',
        'Sports',
        'sports',
        'מכבי',
        'ברצלונה',
        'ריאל',
        'הפועל',
        'בית"ר',
    ]
    theater_terms = ['תיאטרון', 'מחזמר', 'Theater', 'theater', 'Musical', 'musical']
    international_names = ['Taylor Swift', 'Bruno Mars', 'Coldplay']

    for artist in Artist.objects.all().iterator():
        haystack = ' '.join(
            [
                artist.name or '',
                getattr(artist, 'genre', None) or '',
                getattr(artist, 'description', None) or '',
            ]
        )
        category = 'music'
        if any(term in haystack for term in sports_terms):
            category = 'sports'
        elif any(term in haystack for term in standup_terms):
            category = 'standup'
        elif any(term in haystack for term in theater_terms):
            category = 'theater'

        is_international = artist.name in international_names
        Artist.objects.filter(pk=artist.pk).update(
            category=category,
            is_international=is_international,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0060_seller_payout_fee_help_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='artist',
            name='category',
            field=models.CharField(
                choices=[
                    ('music', 'Music'),
                    ('standup', 'Standup'),
                    ('sports', 'Sports'),
                    ('theater', 'Theater'),
                ],
                default='music',
                help_text='Homepage category for marketplace discovery rows',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='artist',
            name='is_international',
            field=models.BooleanField(
                default=False,
                help_text='Hide from local-market homepage discovery when enabled',
            ),
        ),
        migrations.RunPython(backfill_artist_market_fields, noop_reverse),
    ]
