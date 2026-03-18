# Generated manually for adding is_together field to Ticket model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_alter_ticket_asking_price_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='is_together',
            field=models.BooleanField(default=True, help_text='Are the seats together (next to each other)?'),
        ),
    ]






