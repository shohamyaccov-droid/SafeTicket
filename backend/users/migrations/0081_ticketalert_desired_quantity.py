from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0080_ticket_allow_negotiation'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketalert',
            name='desired_quantity',
            field=models.PositiveIntegerField(
                blank=True,
                default=None,
                help_text='Desired ticket count. Null/0 = any quantity (ברירת מחדל).',
                null=True,
            ),
        ),
    ]
