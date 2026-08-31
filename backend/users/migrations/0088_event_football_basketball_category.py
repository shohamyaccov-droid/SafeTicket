from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0087_payme_webhook_idempotency'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='category',
            field=models.CharField(
                choices=[
                    ('concert', 'הופעות'),
                    ('sport', 'ספורט'),
                    ('football', 'כדורגל'),
                    ('basketball', 'כדורסל'),
                    ('theater', 'תיאטרון'),
                    ('festival', 'פסטיבלים'),
                    ('standup', 'סטנדאפ'),
                ],
                default='concert',
                help_text='Event category (concert, football, basketball, sport, …)',
                max_length=50,
            ),
        ),
    ]
