from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0062_secure_ticket_storage_paths'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='guest_first_name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='guest_last_name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
