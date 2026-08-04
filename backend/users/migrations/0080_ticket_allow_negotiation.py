from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0079_announcementbanner'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='allow_negotiation',
            field=models.BooleanField(
                default=True,
                help_text='When True, buyers may submit price offers on this listing.',
            ),
        ),
    ]
