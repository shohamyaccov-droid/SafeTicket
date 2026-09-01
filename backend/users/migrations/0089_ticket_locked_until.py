from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0088_event_football_basketball_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='locked_until',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text='When the temporary cart/PayMe hold expires. Stage 1 (Buy Now) is 2 minutes; stage 2 (order created) is 10 minutes.',
                null=True,
            ),
        ),
    ]
