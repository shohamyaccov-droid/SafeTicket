from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0074_offer_integrity_constraints'),
    ]

    operations = [
        migrations.AlterField(
            model_name='offer',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('accepted', 'Accepted'),
                    ('rejected', 'Rejected'),
                    ('countered', 'Countered'),
                    ('expired', 'Expired'),
                    ('completed', 'Completed'),
                ],
                default='pending',
                help_text='Current status of the offer',
                max_length=20,
            ),
        ),
    ]
