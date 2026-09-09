# Generated migration for SellerReminder model
# This migration creates the seller_reminder table to track sent reminders

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0089_ticket_locked_until'),
    ]

    operations = [
        migrations.CreateModel(
            name='SellerReminder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seller_reminders', to=settings.AUTH_USER_MODEL)),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reminders_sent', to='users.ticket')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='sellerreminder',
            index=models.Index(fields=['seller', 'created_at'], name='users_selle_seller__0ca1f0_idx'),
        ),
        migrations.AddIndex(
            model_name='sellerreminder',
            index=models.Index(fields=['ticket', 'created_at'], name='users_selle_ticket__4f1c2e_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='sellerreminder',
            unique_together={('seller', 'ticket')},
        ),
    ]
