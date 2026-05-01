from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0050_fix_menora_venue_sections'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='receipt_file',
            field=models.FileField(
                blank=True,
                help_text='Optional proof of purchase / receipt file',
                null=True,
                upload_to='tickets/receipts/',
            ),
        ),
    ]
