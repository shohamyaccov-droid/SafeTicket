from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0058_ticket_alert_user_artist'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='ends_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the show ends (optional). Escrow payout uses ends_at + 36h when set; else date + 36h.',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='order',
            name='payout_eligible_date',
            field=models.DateTimeField(
                blank=True,
                help_text='When seller payout becomes eligible (36 hours after event)',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='order',
            name='payout_status',
            field=models.CharField(
                choices=[('locked', 'Locked'), ('eligible', 'Eligible'), ('paid', 'Paid')],
                default='locked',
                help_text='Escrow lifecycle: locked -> eligible (after event+36h) -> paid',
                max_length=20,
            ),
        ),
    ]
