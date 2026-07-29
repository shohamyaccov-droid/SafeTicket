from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0078_ticket_eligible_for_bonus'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnnouncementBanner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('banner_text', models.TextField(blank=True, default='', help_text='Top-of-site announcement text shown when active.')),
                ('is_active', models.BooleanField(default=False, help_text='When enabled, show the announcement banner across the site.')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Announcement banner',
                'verbose_name_plural': 'Announcement banner',
            },
        ),
    ]
