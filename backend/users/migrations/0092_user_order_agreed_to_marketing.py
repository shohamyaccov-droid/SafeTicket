from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0091_ticketalert_watched_events'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='agreed_to_marketing',
            field=models.BooleanField(
                default=False,
                help_text='Explicit opt-in to marketing email/WhatsApp (Israeli spam law). Never default True.',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='agreed_to_marketing',
            field=models.BooleanField(
                default=False,
                help_text='Checkout marketing opt-in captured for this order (guest or registered).',
            ),
        ),
    ]
