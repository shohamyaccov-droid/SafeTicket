# Generated manually — hybrid seating / progressive venue map

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0039_multi_currency_and_event_ends_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='Venue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('city', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name', 'city'],
            },
        ),
        migrations.CreateModel(
            name='VenueSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'venue',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='sections',
                        to='users.venue',
                    ),
                ),
            ],
            options={
                'ordering': ['venue', 'name'],
            },
        ),
        migrations.AddConstraint(
            model_name='venue',
            constraint=models.UniqueConstraint(fields=('name', 'city'), name='users_venue_unique_name_city'),
        ),
        migrations.AddConstraint(
            model_name='venuesection',
            constraint=models.UniqueConstraint(fields=('venue', 'name'), name='users_venuesection_unique_venue_name'),
        ),
        migrations.AddField(
            model_name='event',
            name='venue_place',
            field=models.ForeignKey(
                blank=True,
                help_text='Optional structured venue (seating sections); leave empty for legacy/text-only events.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='events',
                to='users.venue',
            ),
        ),
        migrations.RenameField(
            model_name='ticket',
            old_name='section',
            new_name='section_legacy',
        ),
        migrations.AddField(
            model_name='ticket',
            name='custom_section_text',
            field=models.CharField(
                blank=True,
                help_text='User-entered section when no structured sections exist',
                max_length=100,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='ticket',
            name='venue_section',
            field=models.ForeignKey(
                blank=True,
                help_text='Structured section when the event venue defines sections',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tickets',
                to='users.venuesection',
            ),
        ),
    ]
