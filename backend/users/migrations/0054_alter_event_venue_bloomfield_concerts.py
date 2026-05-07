from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0053_seed_four_sports_events_may_2026'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='venue',
            field=models.CharField(
                choices=[
                    ('היכל מנורה מבטחים', 'היכל מנורה מבטחים'),
                    ('אצטדיון בלומפילד', 'אצטדיון בלומפילד'),
                    ('אצטדיון בלומפילד (הופעות)', 'אצטדיון בלומפילד (הופעות)'),
                    ('פיס ארנה ירושלים', 'פיס ארנה ירושלים'),
                    ('סמי עופר', 'סמי עופר'),
                    ('בארבי תל אביב', 'בארבי תל אביב'),
                    ('אחר', 'אחר'),
                ],
                default='היכל מנורה מבטחים',
                help_text='Venue name',
                max_length=255,
            ),
        ),
    ]
