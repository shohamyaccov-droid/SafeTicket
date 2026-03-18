# Generated migration for adding quantity field to Order model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_alter_ticket_pdf_file_alter_ticket_seat_row'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='quantity',
            field=models.IntegerField(default=1, help_text='Number of tickets purchased in this order'),
        ),
    ]






