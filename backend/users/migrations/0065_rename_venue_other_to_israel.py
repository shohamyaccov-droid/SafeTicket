from django.db import migrations, models


def rename_venue_other_to_israel(apps, schema_editor):
    Event = apps.get_model('users', 'Event')
    Event.objects.filter(venue='אחר').update(venue='ישראל')


def rename_venue_israel_to_other(apps, schema_editor):
    Event = apps.get_model('users', 'Event')
    Event.objects.filter(venue='ישראל').update(venue='אחר')


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0064_user_bit_phone_number_user_payout_method'),
    ]

    operations = [
        migrations.RunPython(rename_venue_other_to_israel, rename_venue_israel_to_other),
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
                    ('ישראל', 'ישראל'),
                ],
                default='היכל מנורה מבטחים',
                help_text='Venue name',
                max_length=255,
            ),
        ),
    ]
