from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0069_event_seo_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending_approval', 'Pending Approval'),
                    ('active', 'Active'),
                    ('reserved', 'Reserved'),
                    ('taken', 'Taken'),
                    ('sold', 'Sold'),
                    ('pending_payout', 'Pending Payout'),
                    ('paid_out', 'Paid Out'),
                    ('rejected', 'Rejected'),
                ],
                default='pending_approval',
                max_length=20,
            ),
        ),
    ]
