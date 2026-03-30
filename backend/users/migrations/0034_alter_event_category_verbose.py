# Generated manually for homepage category labels (Hebrew UI parity with product).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0033_seller_onboarding_and_pricing_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='category',
            field=models.CharField(
                choices=[
                    ('concert', 'הופעות'),
                    ('sport', 'ספורט'),
                    ('theater', 'תיאטרון'),
                    ('festival', 'פסטיבלים'),
                    ('standup', 'סטנדאפ'),
                ],
                default='concert',
                help_text='Event category',
                max_length=50,
            ),
        ),
    ]
