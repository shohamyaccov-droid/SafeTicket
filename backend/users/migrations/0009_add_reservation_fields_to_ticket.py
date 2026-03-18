# Generated migration for adding reservation fields to Ticket model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_add_quantity_to_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='reserved_at',
            field=models.DateTimeField(blank=True, help_text='Timestamp when ticket was reserved', null=True),
        ),
        migrations.AddField(
            model_name='ticket',
            name='reserved_by',
            field=models.ForeignKey(blank=True, help_text='User who reserved this ticket (null for guest reservations)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reserved_tickets', to='users.user'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='reservation_email',
            field=models.EmailField(blank=True, help_text='Email of guest who reserved (if not logged in)', max_length=254, null=True),
        ),
        migrations.AlterField(
            model_name='ticket',
            name='status',
            field=models.CharField(choices=[('active', 'Active'), ('reserved', 'Reserved'), ('sold', 'Sold'), ('pending_payout', 'Pending Payout'), ('paid_out', 'Paid Out')], default='active', max_length=20),
        ),
    ]





