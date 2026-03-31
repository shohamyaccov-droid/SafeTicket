# Generated manually: Option A — canonical status pending_approval for manual IL review queue.

from django.db import migrations, models


def forwards_rename_status(apps, schema_editor):
    Ticket = apps.get_model('users', 'Ticket')
    Ticket.objects.filter(status='pending_verification').update(status='pending_approval')


def backwards_rename_status(apps, schema_editor):
    Ticket = apps.get_model('users', 'Ticket')
    Ticket.objects.filter(status='pending_approval').update(status='pending_verification')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0036_event_country_ticket_receipt'),
    ]

    operations = [
        migrations.RunPython(forwards_rename_status, backwards_rename_status),
        migrations.AlterField(
            model_name='ticket',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending_approval', 'Pending Approval'),
                    ('active', 'Active'),
                    ('reserved', 'Reserved'),
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
