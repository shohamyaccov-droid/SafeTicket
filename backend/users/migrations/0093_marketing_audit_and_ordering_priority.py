from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0092_user_order_agreed_to_marketing'),
    ]

    operations = [
        migrations.AddField(
            model_name='artist',
            name='ordering_priority',
            field=models.IntegerField(
                db_index=True,
                default=0,
                help_text='Homepage sort: higher numbers appear first.',
            ),
        ),
        migrations.AddField(
            model_name='event',
            name='ordering_priority',
            field=models.IntegerField(
                db_index=True,
                default=0,
                help_text='Homepage sort: higher numbers appear first.',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='marketing_opt_in_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the user first explicitly opted in to marketing (legal audit trail).',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='marketing_opt_in_ip',
            field=models.GenericIPAddressField(
                blank=True,
                help_text='Client IP at first marketing opt-in (legal audit trail).',
                null=True,
            ),
        ),
        migrations.AlterModelOptions(
            name='artist',
            options={'ordering': ['-ordering_priority', 'name']},
        ),
        migrations.AlterModelOptions(
            name='event',
            options={'ordering': ['-ordering_priority', '-date', 'name']},
        ),
        migrations.AddIndex(
            model_name='artist',
            index=models.Index(fields=['-ordering_priority', 'name'], name='users_artis_orderin_755769_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['-ordering_priority', '-date'], name='users_event_orderin_baedb7_idx'),
        ),
    ]
